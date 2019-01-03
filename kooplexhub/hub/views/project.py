import logging

from django.contrib import messages
from django.conf.urls import url, include
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.html import format_html
import django_tables2 as tables
from django_tables2 import RequestConfig
from django.utils.translation import gettext_lazy as _

from hub.forms import FormProject
from hub.models import Project, UserProjectBinding, Volume
from hub.models import Image

from kooplex.logic import configure_project

logger = logging.getLogger(__name__)

@login_required
def new(request):
    logger.debug("user %s" % request.user)
    user_id = request.POST.get('user_id')
    try:
        assert user_id is not None and int(user_id) == request.user.id, "user id mismatch: %s tries to save %s %s" % (request.user, request.user.id, request.POST.get('user_id'))
        projectname = request.POST.get('name')
        for upb in UserProjectBinding.objects.filter(user = request.user):
            assert upb.project.name != projectname, "Not a unique name"
        form = FormProject(request.POST)
        form.save()
        upb = UserProjectBinding(user = request.user, project = form.instance)
        upb.save()
        messages.info(request, 'Your new project is created')
        return redirect('project:list')
    except Exception as e:
        logger.error("New project not created -- %s" % e)
        messages.error(request, 'Creation of a new project is refused.')
        return redirect('indexpage')
        


@login_required
def listprojects(request):
    """Renders the projectlist page for courses taught."""
    logger.debug('Rendering project.html')
    context_dict = {
        'next_page': 'project:list',
    }
    return render(request, 'project/list.html', context = context_dict)


class ProjectSelectionColumn(tables.Column):
    def render(self, record):
        state = "checked" if record.is_hidden else ""
        return format_html('<input type="checkbox" name="selection" value="%s" %s>' % (record.id, state))

class T_PROJECT(tables.Table):
    id = ProjectSelectionColumn(verbose_name = 'Hide', orderable = False)
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


@login_required
def configure(request, project_id):
    """Handles the project configuration."""
    user = request.user
    logger.debug("method: %s, project id: %s, user: %s" % (request.method, project_id, user))
    try:
        project = Project.get_userproject(project_id = project_id, user = request.user)
    except Project.DoesNotExist:
        messages.error(request, 'Project does not exist')
        return redirect(next_page)
    if request.method == 'POST':
        logger.debug(request.POST)
        button = request.POST.get('button')
    #    if button == 'delete':
    #        if project.owner == request.user:
    #            delete_project(project)
    #        else:
    #            messages.error(request, 'Project %s is not yours' % project)
    #            return redirect('projects')
    #    elif button == 'quit':
    #        if project.owner == request.user:
    #            messages.error(request, 'You are the owner of the project %s, you cannot leave it' % project)
    #            return redirect('projects')
    #        else:
    #            leave_project(project, request.user)
    #    elif button == 'apply':
        if button == 'apply':
    #        collaborators = [ User.objects.get(id = x) for x in request.POST.getlist('collaborators') ]
            volumes = [ Volume.objects.get(id = x) for x in request.POST.getlist('selection') ]
            image = Image.objects.get(name = request.POST['project_image'])
    #        scope = ScopeType.objects.get(name = request.POST['project_scope'])
            description = request.POST.get('description')
            marked_to_remove = configure_project(project, image = image, volumes = volumes, description = description)
            if marked_to_remove:
                messages.info(request, '%d running containers of project %s will be removed when you stop. Changes take effect after a restart.' % (marked_to_remove, project))
        return redirect('list:teaching') #FIXME
    else:
        context_dict = {
            'images': Image.objects.all(),
            'project': project, 
            'enable_image': True,
            'enable_modulevolume': True, 
            'enable_storagevolume': True,
            't_volumes_fun': sel_table(user = user, project = project, volumetype = 'functional'),
            't_volumes_stg': sel_table(user = user, project = project, volumetype = 'storage'),
        }
        return render(request, 'project/settings.html', context = context_dict)


@login_required
def show_hide(request, next_page):
    """Manage your projects"""
    user = request.user
    logger.debug("user %s method %s" % (user, request.method))
    userprojectbindings = user.profile.projectbindings
    userprojectbindings_course = user.profile.courseprojects_taught_NEW() #FIXME: diak is hideolhat ?
    if request.method == 'GET':
        table_project = T_PROJECT(userprojectbindings)
        table_course = T_PROJECT(userprojectbindings_course)
        RequestConfig(request).configure(table_project)
        RequestConfig(request).configure(table_course)
        context_dict = {
            't_project': table_project,
            't_course': table_course,
            'next_page': next_page,
        }
        return render(request, 'project/manage.html', context = context_dict)
    else:
        hide_bindingids_req = set([ int(i) for i in request.POST.getlist('selection') ])
        n_hide = 0
        n_unhide = 0
        for upb in set(userprojectbindings).union(userprojectbindings_course):
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
        return redirect(next_page)

@login_required
def hide(request, project_id, next_page):
    """Hide project from the list."""
    logger.debug("project id %s, user %s" % (project_id, request.user))
    try:
        project = Project.objects.get(id = project_id)
        UserProjectBinding.setvisibility(project, request.user, hide = True)
    except Project.DoesNotExist:
        messages.error(request, 'You cannot hide the requested project.')
    except ProjectDoesNotExist:
        messages.error(request, 'You cannot hide the requested project.')
    return redirect(next_page)


urlpatterns = [
    url(r'^list', listprojects, name = 'list'), 

    url(r'^new/?$', new, name = 'new'), 

    url(r'^configure/(?P<project_id>\d+)$', configure, name = 'configure'), 
    url(r'^show/(?P<next_page>\w+:?\w*)$', show_hide, name = 'showhide'),
    url(r'^hide/(?P<project_id>\d+)/(?P<next_page>\w+:?\w*)$', hide, name = 'hide'), 
]

