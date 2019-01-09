from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
import django_tables2 as tables

from hub.models import UserProjectBinding
from hub.models import ProjectContainerBinding

def select_column(container):
    class SelectColumn(tables.Column):
        def render(self, record):
            p = record.project
            try:
                ProjectContainerBinding.objects.get(container = container, project = p)
                s = "checked"
            except ProjectContainerBinding.DoesNotExist:
                s = ""
            return format_html("<input type='checkbox' name='project_ids' value='%d' %s>" % (p.id, s))
    return SelectColumn

def image_column(container):
    class ImageColumn(tables.Column):
        def render(self, record):
            image = record.project.image
            return format_html(str(image)) if image == container.image else format_html("<strong>%s</strong>" % image)
    return ImageColumn

def table_projects(container):
    rc = select_column(container)
    ic = image_column(container)
    class T_PROJECTS(tables.Table):
        id = rc(verbose_name = 'Select', orderable = False)
        project = tables.Column(orderable = False)
        user = ic(verbose_name = 'Image', orderable = False) #FIXME: we are abusing this field !!!!
    
        class Meta:
            model = UserProjectBinding
            fields = ('id', 'project')
            #sequence = ('id', 'user', 'location', 'bio')
            attrs = { "class": "table-striped table-bordered", "td": { "style": "padding:.5ex" } }

    return T_PROJECTS

class SelectColumn(tables.Column):
    def render(self, record):
        p = record.project
        return format_html("<input type='checkbox' name='project_ids' value='%d'>" % (p.id))

class ProjectColumn(tables.Column):
    def render(self, record):
        p = record.project
        return format_html("%s (%s)" % (p.name, p.image))

class UserColumn(tables.Column):
    def render(self, record):
        u = record.user
        return format_html("%s %s (%s)" % (u.first_name, u.last_name, u.username))

class T_JOINABLEPROJECT(tables.Table):
    id = SelectColumn(verbose_name = 'Select', orderable = False)
    project = ProjectColumn(verbose_name = 'Project (image)', orderable = False)
    user = UserColumn(verbose_name = 'Creator name', orderable = False)
    class Meta:
        model = UserProjectBinding
        fields = ('id', 'project', 'user')
        sequence = ('id', 'project', 'user')
        attrs = { "class": "table-striped table-bordered", "td": { "style": "padding:.5ex" } }