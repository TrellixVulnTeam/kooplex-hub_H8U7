import logging

from django.contrib import messages
from django.conf.urls import url, include
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils.html import format_html
import django_tables2 as tables
from django_tables2 import RequestConfig
from django.utils.translation import gettext_lazy as _
from django.db.models import Q


from hub.forms import FormProject
from hub.forms import table_collaboration, T_SERVICE, T_JOINABLEPROJECT
from hub.forms import table_volume
from hub.forms import table_vcproject
from hub.models import Project, UserProjectBinding
from hub.models import Service, ProjectServiceBinding
from hub.models import Volume
from hub.models import Image
from hub.models import Profile
from hub.models import VCProject
from hub.models import FSLibrary

from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)

@login_required
def new(request):
    logger.debug("user %s" % request.user)
    user_id = request.POST.get('user_id')
    try:
        assert user_id is not None and int(user_id) == request.user.id, f'user id mismatch {request.user}: {request.user_id} =/= {user_id}'
        form = FormProject(request.POST, user = request.user)
        if form.is_valid():
            logger.info(form.cleaned_data)
            projectname = form.cleaned_data['name']
            for upb in UserProjectBinding.objects.filter(user = request.user):
                if upb.project.name == projectname:
                    msg = f'Project name {projectname} is not unique'
                    messages.error(request, msg)
                    raise Exception(msg)
            project = Project.objects.create(name = projectname, description = form.cleaned_data['description'])
            UserProjectBinding.objects.create(user = request.user, project = project, role = UserProjectBinding.RL_CREATOR)
            messages.info(request, f'New project {project} is created')
            if len(form.cleaned_data['environments']) > 0:
                for svc in form.cleaned_data['environments']:
                    ProjectServiceBinding.objects.create(project = project, service = svc)
                    if svc.state == svc.ST_RUNNING:
                        svc.state = svc.ST_NEED_RESTART
                        svc.save()
                        messages.warning(request, f'Project {project} is added to running svc {svc.name}, which requires a restart to apply changes')
                    else:
                        messages.info(request, f'Project {project} is added to svc {svc.name}')
            else:
                image = Image.objects.all().first() #TODO: make it possible to select a default
                svc = Service.objects.create(name = projectname, user = request.user, image = image)
                ProjectServiceBinding.objects.create(project = project, service = svc)
                messages.info(request, f'New service {svc.name} is created with image {svc.image.name}')
        return redirect('project:list')
    except Exception as e:
        logger.error(f'New project not created -- {e}')
        messages.error(request, 'Creation of a new project is refused.')
        return redirect('indexpage')
        

@login_required
def join(request):
    logger.debug("user %s" % request.user)
    user = request.user
    if request.method == 'GET':
        project_public_and_internal = set(Project.objects.filter(Q(scope = Project.SCP_INTERNAL) | Q(scope = Project.SCP_PUBLIC)))
        project_mine = set([ upb.project for upb in UserProjectBinding.objects.filter(user = user) ])
        project_joinable = project_public_and_internal.difference(project_mine)
        table_joinable = T_JOINABLEPROJECT([ UserProjectBinding.objects.get(project = p, role = UserProjectBinding.RL_CREATOR) for p in project_joinable ])
        RequestConfig(request).configure(table_joinable)
        context_dict = {
            't_joinable': table_joinable,
        }
        return render(request, 'project/join.html', context = context_dict)
    else:
        joined = []
        svcs = []
        for project_id in request.POST.getlist('project_ids'):
            try:
                project = Project.objects.get(id = project_id, scope__in = [ Project.SCP_INTERNAL, Project.SCP_PUBLIC ])
                UserProjectBinding.objects.create(user = user, project = project, role = UserProjectBinding.RL_COLLABORATOR)
                joined.append(project)
                logger.info("%s joined project %s as a member" % (user, project))
                for image_id in request.POST.getlist(f'image_ids_{project_id}'):
                    i = Image.objects.get(id = image_id)
                    svc = Service.objects.create(user = user, image = i, name = f'{user.username}-{project.name}-{project.creator.username}')
                    psb = ProjectServiceBinding.objects.create(project = project, service = svc)
                    logger.info(f'created service {svc} and binding {psb}')
                    svcs.append(svc)
            except Exception as e:
                logger.warning("%s cannot join project id %s -- %s" % (user, project_id, e))
                messages.error(request, 'You cannot join project')
        if len(joined):
            messages.info(request, 'Joined projects: {}'.format(', '.join([ p.name for p in joined ])))
        if len(svcs):
            messages.info(request, 'Created services: {}'.format(', '.join([ s.name for s in svcs ])))

        return redirect('project:list')


@login_required
def listprojects(request):
    """Renders the projectlist page for courses taught."""
    logger.debug('Rendering project.html')
    context_dict = {
        'menu_project': 'active',
    }
    return render(request, 'project/list.html', context = context_dict)


#FIXME: place in forms
class ProjectSelectionColumn(tables.Column):
    def render(self, record):
        if record.is_hidden:
            return format_html('<input type="checkbox" name="selection" data-toggle="toggle" value="{0}" data-off="Show" data-on="Hidden" data-onstyle="dark" data-offstyle="success" data-size="xs" checked>'.format(record.id))
        else:
            return format_html('<input type="checkbox" name="selection" data-toggle="toggle" value="{0}" data-off="Shown" data-on="Hide" data-onstyle="dark" data-offstyle="success" data-size="xs">'.format(record.id))


class T_PROJECT(tables.Table):
    id = ProjectSelectionColumn(verbose_name = 'Visibility', orderable = False)
    class Meta:
        model = UserProjectBinding
        fields = ('id', 'project')
        sequence = ('id', 'project')
        attrs = { "class": "table-striped table-bordered", "td": { "style": "padding:.5ex" } }

def sel_col(project):
    class VolumeSelectionColumn(tables.Column):
        def render(self, record):
            state = "checked" if record in project.volumes else ""
            return format_html('<input type="checkbox" name="selection" value="%s" %s>' % (record.id, state))
    return VolumeSelectionColumn

def sel_table(user, project, volumetype):
    if volumetype == 'functional': #FIXME: Volume.FUNCTIONAL
        user_volumes = user.profile.functional_volumes
    elif volumetype == 'storage':
        user_volumes = user.profile.storage_volumes
    column = sel_col(project)

    class T_VOLUME(tables.Table):
        id = column(verbose_name = 'Selection')
    
        class Meta:
            model = Volume
            exclude = ('name', 'volumetype')
            attrs = { "class": "table-striped table-bordered", "td": { "style": "padding:.5ex" } }
    return T_VOLUME(user_volumes)
########################

@login_required
def configure(request, project_id):
    user = request.user
    logger.debug("method: %s, project id: %s, user: %s" % (request.method, project_id, user))
    try:
        project = Project.get_userproject(project_id = project_id, user = request.user)
    except Project.DoesNotExist as e:
        logger.error('abuse by %s project id: %s -- %s' % (user, project_id, e))
        messages.error(request, 'Project does not exist')
        return redirect('project:list')

    if request.method == 'POST' and request.POST.get('button') == 'apply':

        # meta
        project.scope = request.POST['project_scope']
        project.description = request.POST.get('description')
        project.save()
        
        assert project.is_admin(user), "You don't have the necessary rights"
        # collaboration
        collaborator_ids_before = set(request.POST.getlist('collaborator_ids_before'))
        collaborator_ids_after = set(request.POST.getlist('collaborator_ids_after'))
        admin_ids_before = set(request.POST.getlist('admin_ids_before'))
        admin_ids_after = set(request.POST.getlist('admin_ids_after'))

        # removal
        removed = []
        collaborator_ids_to_remove = collaborator_ids_before.difference(collaborator_ids_after)
        for i in collaborator_ids_to_remove:
            b = UserProjectBinding.objects.get(user__id = i, project = project)
            removed.append(b.user.username)
            b.delete()

        # addition
        added = []
        service_ids = request.POST.getlist('service_ids')
        collaborator_ids_to_add = collaborator_ids_after.difference(collaborator_ids_before)
        for i in collaborator_ids_to_add:
            collaborator = User.objects.get(id = i)
            if i in admin_ids_after:
                b = UserProjectBinding.objects.create(user = collaborator, project = project, role = UserProjectBinding.RL_ADMIN)
            else:
                b = UserProjectBinding.objects.create(user = collaborator, project = project, role = UserProjectBinding.RL_COLLABORATOR)
            added.append(b.user.username)
            # copy service information
            for sid in service_ids:
                svc = ProjectServiceBinding.objects.get(id = sid, service__user = user).service
                svc_copy = Service.objects.create(user = collaborator, image = svc.image, name = f'{b.user.username}-{project.name}-{user.username}')
                ProjectServiceBinding.objects.create(service = svc_copy, project = project)
                #TODO: handle volumes

        # role change
        changed = []
        collaborator_ids_to_admin = admin_ids_after.difference(admin_ids_before).intersection(collaborator_ids_after).difference(collaborator_ids_to_add)
        collaborator_ids_to_revokeadmin = admin_ids_before.difference(admin_ids_after).intersection(collaborator_ids_after).difference(collaborator_ids_to_add)
        for i in collaborator_ids_to_admin:
            b = UserProjectBinding.objects.filter(user__id = i, project = project).exclude(role = UserProjectBinding.RL_CREATOR)
            assert len(b) == 1
            b = b[0]
            b.role = UserProjectBinding.RL_ADMIN
            changed.append(b.user.username)
            b.save()
        for i in collaborator_ids_to_revokeadmin:
            b = UserProjectBinding.objects.filter(user__id = i, project = project).exclude(role = UserProjectBinding.RL_CREATOR)
            assert len(b) == 1
            b = b[0]
            b.role = UserProjectBinding.RL_COLLABORATOR
            changed.append(b.user.username)
            b.save()

        if added:
            messages.info(request, 'Added {} as colaborators'.format(', '.join(added)))
        if removed:
            messages.info(request, 'Removed {} from colaboration'.format(', '.join(removed)))
        if changed:
            messages.info(request, 'Changed collaboration roles of {}'.format(', '.join(changed)))


        return redirect('project:list')
    else:
        if project.is_admin(user):
            table = table_collaboration(project)
            table_collaborators = table(user.profile.everybodyelse) #FIXME: if pattern == '' else table(user.profile.everybodyelse_like(pattern))
            RequestConfig(request).configure(table_collaborators)

            table_services = T_SERVICE(ProjectServiceBinding.objects.filter(service__user = user, project = project))
            RequestConfig(request).configure(table_services)
        else:
            table_collaborators = None
        context_dict = {
            'project': project, 
            't_collaborators': table_collaborators,
            't_services': table_services,
        }
        return render(request, 'project/configure.html', context = context_dict)


#    sort_info = request.GET.get('sort') if request.method == 'GET' else request.POST.get('sort')
#    if request.method == 'POST' and request.POST.get('button') == 'apply':
#        msg = project.set_roles(request.POST.getlist('role_map'))
#        if len(msg):
#            messages.info(request, '\n'.join(msg))
#        return redirect(next_page)
#    elif (request.method == 'POST' and request.POST.get('button') == 'search') or request.method == 'GET':
#        pattern = request.POST.get('name', '')
#        context_dict = {
#            'project': project, 
#            'can_configure': True,
#            'submenu': 'collaboration',
#            'next_page': next_page,
#            'search_name': pattern,
#            'sort': sort_info,
#        }
#        return render(request, 'project/conf-collaboration.html', context = context_dict)
#    elif request.method == 'POST' and request.POST.get('button') == 'cancel':
#        context_dict = {
#             'next_page': 'project:list',
#             'menu_project': 'active',
#        }
#        return render(request, 'project/list.html', context = context_dict)




#@login_required
#def conf_versioncontrol(request, project_id, next_page):
#    user = request.user
#    logger.debug("method: %s, project id: %s, user: %s" % (request.method, project_id, user))
#    try:
#        project = Project.get_userproject(project_id = project_id, user = request.user)
#        assert project.is_admin(user), "%s is not admin of %s" % (user, project)
#    except Exception as e:
#        logger.error('abuse by %s project id: %s -- %s' % (user, project_id, e))
#        messages.error(request, 'Unauthorized request.')
#        return redirect(next_page)
#
#    sort_info = request.GET.get('sort') if request.method == 'GET' else request.POST.get('sort')
#    if request.method == 'POST' and request.POST.get('button') == 'apply':
#        msgs = []
#        for id_create in request.POST.getlist('vcp_ids'):
#            vcp = VCProject.objects.get(id = id_create)
#            if vcp.token.user != user:
#                logger.error("Unauthorized request vcp: %s, user: %s" % (vcp, user))
#                continue
#            VCProjectProjectBinding.objects.create(project = project, vcproject = vcp)
#            msgs.append('Bound %s to repository %s.' % (project, vcp))
#        for id_remove in set(request.POST.getlist('vcppb_ids_before')).difference(set(request.POST.getlist('vcppb_ids_after'))):
#            try:
#                vcppb = VCProjectProjectBinding.objects.get(id = id_remove, project = project)
#                if vcppb.vcproject.token.user != user:
#                    logger.error("Unauthorized request vcp: %s, user: %s" % (vcp, user))
#                    continue
#                msgs.append('Project %s is not bound to repository %s any more.' % (project, vcppb.vcproject))
#                vcppb.delete()
#            except VCProjectProjectBinding.DoesNotExist:
#                logger.error("Is %s hacking" % user)
#        if len(msgs):
#            messages.info(request, ' '.join(msgs))
#        return redirect(next_page)
#    elif (request.method == 'POST' and request.POST.get('button') == 'search') or request.method == 'GET':
#        t = table_vcproject(project)
#        pattern = request.POST.get('repository', '')
#        qs = VCProject.objects.filter(token__user = user, cloned = True) if pattern == '' else VCProject.objects.filter(token__user = user, cloned = True, project_name__icontains = pattern)
#        table_vcp = t(qs)
#        RequestConfig(request).configure(table_vcp)
#        context_dict = {
#            'project': project, 
#            't_vcp': table_vcp, 
#            'submenu': 'versioncontrol',
#            'next_page': next_page,
#            'search_repository': pattern,
#            'sort': sort_info,
#        }
#        return render(request, 'project/conf-versioncontrol.html', context = context_dict)
#    elif request.method == 'POST' and request.POST.get('button') == 'cancel':
#        context_dict = {
#             'next_page': 'project:list',
#             'menu_project': 'active',
#        }
#        return render(request, 'project/list.html', context = context_dict)
#    else:
#        return redirect(next_page)



@login_required
def delete_leave(request, project_id):
    """Delete or leave a project."""
    user = request.user
    logger.debug("method: %s, project id: %s, user: %s" % (request.method, project_id, user))
    try:
        project = Project.get_userproject(project_id = project_id, user = request.user)
        upb = UserProjectBinding.objects.get(user = user, project = project)
    except Project.DoesNotExist:
        messages.error(request, 'Project does not exist')
        return redirect('project:list')
    if upb.role == upb.RL_CREATOR:
        collab = []
        for upb_i in UserProjectBinding.objects.filter(project = project):
            if upb != upb_i:
                collab.append(upb_i.user)
                upb_i.delete()
        upb.delete()
        project.delete()
        if len(collab):
            messages.info(request, 'Users removed from collaboration: {}'.format(', '.join([  f'{u.first_name} {u.last_name} ({u.username})' for u in collab ])))
        messages.info(request, 'Project %s is deleted' % (project))
    else:
        upb.delete()
        messages.info(request, 'You left project %s' % (project))
    return redirect('project:list')


@login_required
def show_hide(request):
    """Manage your projects"""
    user = request.user
    logger.debug("user %s method %s" % (user, request.method))
    userprojectbindings = user.profile.projectbindings
    if request.method == 'GET':
        table_project = T_PROJECT(userprojectbindings)
        RequestConfig(request).configure(table_project)
        context_dict = {
            't_project': table_project,
        }
        return render(request, 'project/manage.html', context = context_dict)
    else:
        hide_bindingids_req = set([ int(i) for i in request.POST.getlist('selection') ])
        n_hide = 0
        n_unhide = 0
        for upb in set(userprojectbindings):#.union(userprojectbindings_course):
            if upb.is_hidden and not upb.id in hide_bindingids_req:
                upb.is_hidden = False
                upb.save()
                n_unhide += 1
            elif not upb.is_hidden and upb.id in hide_bindingids_req:
                upb.is_hidden = True
                upb.save()
                n_hide += 1
        msgs = []
        if n_hide:
            msgs.append('%d projects are hidden.' % n_hide)
        if n_unhide:
            msgs.append('%d projects are unhidden.' % n_unhide)
        if len(msgs):
            messages.info(request, ' '.join(msgs))
        return redirect('project:list')

@login_required
def hide(request, project_id):
    """Hide project from the list."""
    logger.debug("project id %s, user %s" % (project_id, request.user))
    try:
        project = Project.objects.get(id = project_id)
        UserProjectBinding.setvisibility(project, request.user, hide = True)
    except Project.DoesNotExist:
        messages.error(request, 'You cannot hide the requested project.')
    except ProjectDoesNotExist:
        messages.error(request, 'You cannot hide the requested project.')
    return redirect('project:list')



@login_required
def stat(request):
    logger.debug('Printing stats')
    from pandas import DataFrame 
    from django_pandas.io import read_frame

    uprojects = UserProjectBinding.objects.all()
    if len(list(uprojects)) == 0:
        df_uprojects = DataFrame()
    else:
        try:
            df_uprojects = read_frame(uprojects)
            df_p_count = df_uprojects.groupby(['project']).count().drop(['is_hidden', 'id', 'role'], axis=1)#, values='score')
        except Exception as e:
            logger.error("Invalid request with ??? %s"% e)

    from hub.models import UserCourseBinding
    ucourses = UserCourseBinding.objects.all()
    if len(list(uprojects)) == 0:
        df_ucourses = DataFrame()
    else:
        try:
            df_ucourses = read_frame(ucourses)
            df_c_count = df_ucourses.groupby(['course']).count().drop(['id', 'is_teacher', 'is_protected'], axis=1)
        except Exception as e:
            logger.error("Invalid request with ??? %s"% e)
    context_dict = {
            'uprojects': df_p_count.to_html(table_id='datatable', col_space=100),
            'ucourses': df_c_count.to_html(table_id='datatable', col_space=100),

        }
    return render(request, 'project/statistics.html', context = context_dict)

urlpatterns = [
    url(r'^list', listprojects, name = 'list'), 
    url(r'^new/?$', new, name = 'new'), 
    url(r'^show/?$', show_hide, name = 'showhide'),
    url(r'^hide/(?P<project_id>\d+)/?$', hide, name = 'hide'), 
    url(r'^delete/(?P<project_id>\d+)/?$', delete_leave, name = 'delete'), 
    url(r'^configure/(?P<project_id>\d+)/?$', configure, name = 'configure'), 


    #FIXME:
    url(r'^join/?$', join, name = 'join'), 
#    url(r'^configure/(?P<project_id>\d+)/meta/(?P<next_page>\w+:?\w*)$', conf_meta, name = 'conf_meta'), 
#    url(r'^configure/(?P<project_id>\d+)/collaboration/(?P<next_page>\w+:?\w*)$', conf_collab, name = 'conf_collaboration'), 
#    url(r'^configure/(?P<project_id>\d+)/environment/(?P<next_page>\w+:?\w*)$', conf_environment, name = 'conf_environment'), 
#    url(r'^configure/(?P<project_id>\d+)/storage/(?P<next_page>\w+:?\w*)$', conf_voldata, name = 'conf_storage'), 
#    url(r'^configure/(?P<project_id>\d+)/versioncontrol/(?P<next_page>\w+:?\w*)$', conf_versioncontrol, name = 'conf_versioncontrol'), 
    url(r'^stat', stat, name = 'stat'), 
]

