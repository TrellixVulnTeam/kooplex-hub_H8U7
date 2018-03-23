"""
@author: Jozsef Steger, David Visontai
@summary: project manipulation logic
"""
import logging

from kooplex.lib import Gitlab, Docker
from kooplex.lib.filesystem import mkdir_project, mkdir_git_workdir, cleanup_share, cleanup_git_workdir, create_clone_script
from kooplex.logic.impersonator import mkdir_project_oc, share_project_oc, unshare_project_oc
from kooplex.logic.spawner import remove_container
from kooplex.hub.models import VolumeProjectBinding, UserProjectBinding, ProjectContainer

logger = logging.getLogger(__name__)

def create_project(project, volumes):
    """
    @summary: create a new user project
              1. create gitlab project behalf of the user
              2. save project volume bindings
              3. create share and git workdir
              4. create owncloud workdir
    @param project: the project model
    @type project: kooplex.hub.models.Project
    @param volumes: volumes to bind with the project
    @type volumes: list of kooplex.hub.models.Volume
    """
    logger.debug("%s #volumes %d" % (project, len(volumes)))
    g = Gitlab(project.owner)
    information = g.create_project(project)
    project.save()
    for volume in volumes:
        vpb = VolumeProjectBinding(project = project, volume = volume)
        vpb.save()
        logger.debug("new volume project binding %s" % vpb)
    logger.info("%s created" % project)
    mkdir_project(project.owner, project)
    mkdir_project_oc(project)

def delete_project(project):
    """
    @summary: delete a user project
              1. remove project volume bindings
              2. garbage collect data in share
              3. garbage collect data in git workdir
              4. owncloud unshare
              5. remove user project binding
              6. get rid of containers if any
              7. delete gitlab project on the user's behalf
    @param project: the project model
    @type project: kooplex.hub.models.Project
    """
    logger.debug(project)
    gitlab = Gitlab(project.owner)
    for vpb in VolumeProjectBinding.objects.filter(project = project):
        logger.debug("removed volume project binding %s" % vpb)
        vpb.delete()
    cleanup_share(project)
    cleanup_git_workdir(project.owner, project)
    for upb in UserProjectBinding.objects.filter(project = project):
        logger.debug("removed user project binding %s" % upb)
        unshare_project_oc(project, upb.user)
        gitlab.delete_project_member(project, upb.user)
        cleanup_git_workdir(upb.user, project)
        upb.delete()
    try:
        container = ProjectContainer.objects.get(user = project.owner, project = project)
        logger.debug("remove container %s" % container)
        remove_container(container)
    except ProjectContainer.DoesNotExist:
        logger.debug("%s has no container" % project)
    information = gitlab.delete_project(project)
    logger.info("%s deleted" % project)
    project.delete()

def configure_project(project, image, scope, volumes, collaborators):
    """
    @summary: configure a user project
              1. set image and scope
              2. manage volume project bindings
              3. manage user project bindings and manage gitlab sharing
    @param project: the project model
    @type project: kooplex.hub.models.Project
    @param image: the new image to set
    @type image: kooplex.hub.models.Image
    @param scope: the new scope to set
    @type scope: kooplex.hub.models.ScopeType
    @param volumes: the list of functional and storage volumes
    @type volumes: list(kooplex.hub.models.Volume)
    @param collaborators: the list of users to share the project with as collaboration
    @type collaborators: list(kooplex.hub.models.User)
    @return: bool whether the project containers were marked to be removed after next stop
    """
    mark_to_remove = False
    logger.debug(project)
    if project.image != image:
        project.image = image
        mark_containers_remove(project)
    project.scope = scope
    for vpb in VolumeProjectBinding.objects.filter(project = project):
        if vpb.childvolume in volumes:
            logger.debug("volume project binding remains %s" % vpb)
            volumes.remove(vpb.childvolume)
        else:
            mark_to_remove = True
            logger.debug("volume project binding removed %s" % vpb)
            vpb.delete()
    for volume in volumes:
        mark_to_remove = True
        vpb = VolumeProjectBinding(project = project, volume = volume)
        logger.debug("volume project binding added %s" % vpb)
        vpb.save()
    gitlab = Gitlab(project.owner)
    for upb in UserProjectBinding.objects.filter(project = project):
        if upb.user in collaborators:
            logger.debug("collaborator remains %s" % upb)
            collaborators.remove(upb.user)
        else:
            logger.debug("collaborator removed %s" % upb)
            unshare_project_oc(project, upb.user)
            gitlab.delete_project_member(project, upb.user)
            cleanup_git_workdir(upb.user, project)
            upb.delete()
    for user in collaborators:
        join_project(project, user, gitlab)
    if mark_to_remove:
        mark_containers_remove(project)
    project.save()
    return mark_to_remove

def mark_containers_remove(project):
    """
    @summary: mark project containers to be removed when they are stopped next time. In case the container is already stopped, remove them
    @param project: the project model
    @type project: kooplex.hub.models.Project
    @returns a pair of containers marked to be removed and the number of containers actually removed
    @rtype (int, int)
    """
    n_mark = 0
    n_remove = 0
    for container in project.containers:
        if container.is_running:
            container.mark_to_remove = True
            container.save()
            n_mark += 1
        else:
            Docker().remove_container(container)
            n_remove += 1
    return n_mark, n_remove

def join_project(project, user, gitlab = None):
    """
    @summary: join a user project
              1. add a new user project binding
              2. owncloud share
              3. gitlab project on the user's behalf
    @param project: the project model
    @type project: kooplex.hub.models.Project
    @param user: the collaborator to join the project
    @type user: kooplex.hub.models.User
    @param gitlab: a gitlab driver instance, defaults to None, which means we are initializing a new here
    @type gitlab: kooplex.lib.Gitlab
    """
    if gitlab is None:
        gitlab = Gitlab(project.owner)
    logger.debug(project)
    upb = UserProjectBinding(project = project, user = user)
    logger.debug("collaborator added %s" % upb)
    share_project_oc(project, upb.user)
    gitlab.add_project_member(project, upb.user)
    mkdir_git_workdir(upb.user, project)
    create_clone_script(project, collaboratoruser = upb.user)
    upb.save()
    logger.info("%s joins project %s" % (user, project))

def leave_project(project, user):
    """
    @summary: leave a user project
              1. remove user project binding
              2. garbage collect data in git workdir
              3. owncloud unshare
              6. get rid of containers if any
              7. delete gitlab project on the user's behalf
    @param project: the project model
    @type project: kooplex.hub.models.Project
    @param user: the collaborator to leave the project
    @type user: kooplex.hub.models.User
    """
    logger.debug(project)
    try:
        upb = UserProjectBinding.objects.get(project = project, user = user)
        upb.delete()
        logger.debug('user project binding removed: %s' % upb)
    except UserProjectBinding.DoesNotExist:
        msg = 'user %s is not bound to project %s' % (user, project)
        logger.error(msg)
        return msg
    gitlab = Gitlab(project.owner)
    cleanup_git_workdir(user, project)
    unshare_project_oc(project, user)
    gitlab.delete_project_member(project, user)
    try:
        container = ProjectContainer.objects.get(user = user, project = project)
        logger.debug("remove container %s" % container)
        remove_container(container)
    except ProjectContainer.DoesNotExist:
        logger.debug("%s has no container" % project)
    logger.info("%s left project %s" % (user, project))

