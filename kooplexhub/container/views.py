import logging
import json
import requests

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.html import format_html
from django.views import generic
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import FormContainer, FormAttachment
from .forms import TableContainerProject, TableContainerCourse, TableContainerAttachment, TableContainerVolume
from .models import Image, Container, Attachment, AttachmentContainerBinding
from project.models import Project, UserProjectBinding, ProjectContainerBinding
from education.models import Course, UserCourseBinding, CourseContainerBinding
from volume.models import Volume, VolumeContainerBinding

from kooplexhub.lib import custom_redirect

from kooplexhub import settings

logger = logging.getLogger(__name__)

class NewContainerView(LoginRequiredMixin, generic.FormView):
    template_name = 'container_new.html'
    form_class = FormContainer
    success_url = '/hub/container_environment/list/' #FIXME: django.urls.reverse or shortcuts.reverse does not work reverse('project:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu_container'] = True
        context['submenu'] = 'new'
        return context

    def form_valid(self, form):
        logger.info(form.cleaned_data)
        user = self.request.user
        friendly_name = form.cleaned_data['friendly_name']
        Container.objects.create(
            user = user, 
            name = form.cleaned_data['name'], 
            friendly_name = friendly_name, 
            image = form.cleaned_data['image']
        )
        messages.info(self.request, f'Container {friendly_name} is created')
        return super().form_valid(form)


@login_required
def destroy(request, container_id, next_page):
    """Deletes a container instance"""
    user = request.user
    try:
        container = Container.objects.get(id = container_id, user = user)
        container.stop()
        container.delete()
    except Container.DoesNotExist:
        messages.error(request, 'Container environment does not exist')
    return redirect(next_page)


class ContainerListView(LoginRequiredMixin, generic.ListView):
    template_name = 'container_list.html'
    context_object_name = 'containers'
    model = Container

    def get_context_data(self, **kwargs):
        l = reverse('container:new')
        context = super().get_context_data(**kwargs)
        context['menu_container'] = True
        context['submenu'] = 'list'
        context['partial'] = 'container_partial_list.html'
        context['empty_body'] = format_html(f"""You need to <a href="{l}"><i class="bi bi-boxes"></i><span>&nbsp;create</span></a> environments in order to use the hub.""")
        return context

    def get_queryset(self):
        user = self.request.user
        containers = Container.objects.filter(user = user, image__imagetype = Image.TP_PROJECT).order_by('name')
        return containers

class ReportContainerListView(LoginRequiredMixin, generic.ListView):
    template_name = 'container_list.html'
    context_object_name = 'containers'
    model = Container

    def get_context_data(self, **kwargs):
        l = reverse('report:new')
        context = super().get_context_data(**kwargs)
        context['menu_container'] = True
        context['submenu'] = 'reportclist'
        context['partial'] = 'container_partial_list_report.html'
        context['empty'] = format_html(f"""You need to <a href="{l}"><i class="bi bi-projector"></i><span>&nbsp;create</span></a> a container backed report to see here anything useful.""")
        return context

    def get_queryset(self):
        user = self.request.user
        containers = Container.objects.filter(user = user, image__imagetype = Image.TP_REPORT).order_by('name')
        return containers

class AttachmentListView(LoginRequiredMixin, generic.ListView):
    template_name = 'attachment_list.html'
    context_object_name = 'attachments'
    model = Attachment

    def get_queryset(self):
        user = self.request.user
        profile = user.profile
        attachments = Attachment.objects.all().order_by('name')
        return attachments

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu_storage'] = True
        context['submenu'] = 'list_attachment'
        return context


class NewAttachmentView(LoginRequiredMixin, generic.FormView):
    template_name = 'attachment_new.html'
    form_class = FormAttachment
    success_url = '/hub/container_environment/attachments/' #FIXME: django.urls.reverse or shortcuts.reverse does not work reverse('project:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu_storage'] = True
        context['submenu'] = 'new_attachment'
        return context

    def form_valid(self, form):
        logger.info(form.cleaned_data)
        user = self.request.user
        Attachment.objects.create(creator_id = user.id, name = form.cleaned_data['name'], folder = form.cleaned_data['folder'], description = form.cleaned_data['description'])
        return super().form_valid(form)


@login_required
def configure(request, container_id):
    """Manage your projects"""
    user = request.user
    profile = user.profile
    logger.debug("user %s method %s" % (user, request.method))

    try:
        svc = Container.objects.get(id = container_id, user = user)
    except Container.DoesNotExist:
        logger.error('abuse by %s container id: %s -- %s' % (user, container_id, e))
        messages.error(request, 'Service environment does not exist')
        return redirect('container:list')

    if svc.state == svc.ST_STOPPING:
        messages.error(request, f'Service {svc.name} is still stopping, you cannot configure it right now.')
        return redirect('container:list')
    elif svc.state == svc.ST_STARTING:
        messages.error(request, f'Service {svc.name} is starting up, you cannot configure it right now.')
        return redirect('container:list')

    context_dict = {
        'menu_container': True,
        'active': request.COOKIES.get('configure_env_tab', 'projects'),
        'container': svc,
        'form': FormContainer(container = svc),
        't_attachments': TableContainerAttachment(svc),
        't_projects': TableContainerProject(svc, user),
    }
    if 'volume' in settings.INSTALLED_APPS:
        context_dict['t_volumes'] = TableContainerVolume(svc, user)
    if 'education' in settings.INSTALLED_APPS:
        context_dict['t_courses'] = TableContainerCourse(svc, user)

    return render(request, 'container_configure.html', context = context_dict)


def _helper(request, svc, post_id, binding_model, model_get_authorized, binding_attribute):
    # handle attachment changes
    ids_after = set([ int(i) for i in request.POST.getlist(post_id) ])
    before = { getattr(b, binding_attribute).id: b for b in binding_model.objects.filter(container = svc) }
    #   binding
    info = []
    a = []
    for a_id in ids_after.difference(before.keys()):
        m = model_get_authorized(a_id)
        binding_model.objects.create(**{ 'container': svc, binding_attribute: m })
        a.append(m.name)
    if len(a):
        msg = 'associated {}s {}'.format(binding_attribute, ', '.join(a))
        info.append(msg)
        svc.mark_restart(msg)
    #   unbinding
    a = []
    for a_id in set(before.keys()).difference(ids_after):
        b = before[a_id]
        a.append(getattr(b, binding_attribute).name)
        b.delete()
    if len(a):
        msg = 'removed {}s {}'.format(binding_attribute, ', '.join(a))
        info.append(msg)
        svc.mark_restart(msg)
    return info

@login_required
def configure_save(request):
    if request.POST.get('button', '') == 'cancel':
        return redirect('container:list')
    user = request.user
    try:
        container_id = request.POST['container_id']
        svc = Container.objects.get(id = container_id, user = user)
    except Container.DoesNotExist:
        messages.error(request, 'Service environment does not exist')
        return redirect('container:list')

    info = []

    # handle name change
    friendly_name_before = svc.friendly_name
    friendly_name_after = request.POST.get('friendly_name')
    if friendly_name_before != friendly_name_after:
        svc.friendly_name = friendly_name_after
        svc.save()
        info.append(f'name changed to {friendly_name_after}')

    # handle image change
    image_before = svc.image
    image_after = Image.objects.get(id = request.POST.get('image'))
    if image_before != image_after:
        svc.image = image_after
        svc.save()
        msg = f'image changed from {image_before} to {image_after}'
        info.append(msg)
        svc.mark_restart(msg)

    info.extend( _helper(request, svc, 'attach', AttachmentContainerBinding, lambda x: Attachment.objects.get(id = x), 'attachment') )
    info.extend( _helper(request, svc, 'attach-project', ProjectContainerBinding, lambda x: Project.get_userproject(project_id = x, user = user), 'project') )
    info.extend( _helper(request, svc, 'attach-course', CourseContainerBinding, lambda x: Course.get_usercourse(course_id = x, user = user), 'course') )
    info.extend( _helper(request, svc, 'volume', VolumeContainerBinding, lambda x: Volume.objects.get(id = x), 'volume') ) # FIXME: authorize only those volumes user has right to

    if len(info):
        info = ', '.join(info)
        messages.info(request, f'Service {svc.name} is configured: {info}.')

    return redirect('container:list')


@login_required
def start(request, container_id, next_page):
    """Starts the container."""
    user = request.user

    try:
        svc = Container.objects.get(user = user, id = container_id)
        if svc.state == Container.ST_NOTPRESENT:
            if svc.start().wait(timeout = 10):
                messages.info(request, f'Service {svc.name} is started.')
            else:
                messages.warning(request, f'Service {svc.name} did not start within 10 seconds, reload the page later to check if it is already ready.')
        elif svc.state == Container.ST_STOPPING:
            messages.warning(request, f'Wait a second service {svc.name} is still stopping.')
        elif svc.state == Container.ST_STARTING:
            messages.warning(request, f'Wait a second service {svc.name} is starting.')
        else:
            messages.warning(request, f'Not starting service {svc.name}, which is already running.')
    except Container.DoesNotExist:
        messages.error(request, 'Service environment does not exist')
    except Exception as e:
        logger.error(f'Cannot start the environment {svc} -- {e}')
        messages.error(request, f'Cannot start service environment {e}')
    return redirect(next_page)


def _get_cookie(request):
    try:
        cv = request.COOKIES.get('show_container', '[]')
        return set( json.loads( cv.replace('%5B', '[').replace('%2C', ',').replace('%5D', ']') ) )
    except Exception:
        logger.error('stupid cookie value: {cv}')
        return set()


@login_required
def refresh(request, container_id):
    user = request.user

    try:
        svc = Container.objects.get(user = user, id = container_id)
        svc.check_state()
    except Container.DoesNotExist:
        messages.error(request, 'Environment does not exist')
    except Exception as e:
        logger.error(f'Cannot refresh service environment information {svc} -- {e}')
        messages.error(request, f'Cannot refresh service environment information {svc}')
    next_page = request.COOKIES.get('next_page', 'container:list').replace('%3A', ':')
    redirection = redirect(next_page)
    shown = _get_cookie(request)
    shown.add( svc.id )
    redirection.set_cookie('show_container', json.dumps( list(shown) ))
    return redirection


@login_required
def stop(request, container_id, next_page):
    """Stops a container"""
    user = request.user
    try:
        svc = Container.objects.get(user = user, id = container_id)
        if svc.stop().wait(timeout = 10):
            messages.info(request, f'Service {svc.name} is stopped.')
        else:
            messages.warning(request, f'Service {svc.name} did not stop within 10 seconds, reload the page later to recheck its state.')
    except Container.DoesNotExist:
        messages.error(request, 'Environment does not exist')
    except Exception as e:
        logger.error(f'Cannot stop the environment {svc} -- {e}')
        messages.error(request, f'Cannot stop environment {e}')
    redirection = redirect(next_page)
    shown = _get_cookie(request)
    if svc.id in shown:
        shown.remove( svc.id )
    redirection.set_cookie('show_container', json.dumps( list(shown) ))
    return redirection


@login_required
def restart(request, container_id, next_page):
    """Restart a container"""
    user = request.user
    try:
        svc = Container.objects.get(user = user, id = container_id)
        ev = svc.restart()
        if ev.wait(timeout = 10):
            messages.info(request, f'Service {svc.name} is restarted.')
        else:
            messages.warning(request, f'Service {svc.name} was stopped and it did not start within 10 seconds, reload the page later to recheck its state.')
    except Container.DoesNotExist:
        messages.error(request, 'Environment does not exist')
    except Exception as e:
        logger.error(f'Cannot restart the environment {svc} -- {e}')
        messages.error(request, f'Cannot restart environment: {e}')
    return redirect(next_page)


@login_required
def open(request, container_id, next_page, shown = "[]"):
    """Opens a container"""
    user = request.user
    #if shown != "[]":
    #    raise Exception(shown)
    
    try:
        container = Container.objects.get(id = container_id, user = user)
        if container.state in [ Container.ST_RUNNING, Container.ST_NEED_RESTART ]:
            logger.debug(f'wait_until_ready {container.url_public}')
            container.wait_until_ready()
            logger.debug(f'try to redirect to url {container.url_public}')
            if container.default_proxy.token_as_argument:
                return custom_redirect(container.url_public, token = container.user.profile.token)
            else:
                return custom_redirect(container.url_public)
        else:
            messages.error(request, f'Cannot open {container.name} of state {container.state}')
    except Container.DoesNotExist:
        messages.error(request, 'Environment is missing')
    except requests.TooManyRedirects:
        messages.error(request, f'Cannot redirect to url {container.url_public}')
    except Exception as e:
        logger.error(f'cannot redirect to url {container.url_public} -- {e}')
        messages.error(request, f'Cannot redirect to url {container.url_public}')
    return redirect(next_page)

