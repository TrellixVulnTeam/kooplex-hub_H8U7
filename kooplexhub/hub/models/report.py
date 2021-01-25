import os
import logging

from django.db import models
from django.utils import timezone
from django.db.models.signals import pre_save, post_save, post_delete, pre_delete
from django.template.defaulttags import register
from django.contrib.auth.models import User
from django.dispatch import receiver

from .project import Project
from .image import Image

from kooplex.settings import KOOPLEX
from kooplex.lib import  standardize_str, now, human_localtime, add_report_nginx_api, remove_report_nginx_api

logger = logging.getLogger(__name__)


class Report(models.Model):
    SC_PRIVATE = 'private'
    SC_INTERNAL = 'internal'
    SC_PUBLIC = 'public'
    SC_LOOKUP = {
        SC_PRIVATE: 'private - Only the creator can view the report.',
        SC_INTERNAL: 'internal - The creator and collaborators can view the report.',
        SC_PUBLIC: 'public - Anyone can view the report.',
    }
    name = models.CharField(max_length = 200, null = False)
    description = models.TextField(max_length = 500, null = True, default = None)
    creator = models.ForeignKey(User, null = False)
    project = models.ForeignKey(Project, null = False)
    scope = models.CharField(max_length = 16, choices = SC_LOOKUP.items(), default = SC_INTERNAL)
    created_at = models.DateTimeField(default = timezone.now)
    image = models.ForeignKey(Image, null = False)

    folder = models.CharField(max_length = 200, null = False)
    index = models.CharField(max_length = 128, null = True, default = None)

    password = models.CharField(max_length = 64, null = True, default = None, blank=True)

    class Meta:
        unique_together = [['name']]


    def __lt__(self, c):
        return self.launched_at < c.launched_at

    def __str__(self):
        return "<Report %s@%s>" % (self.name, self.creator)

    @property
    def cleanname(self):
        return standardize_str(self.name)

    @property
    def ts_human(self):
        return human_localtime(self.created_at)

    @property
    def service(self):
        from .service import ReportServiceBinding
        return ReportServiceBinding.objects.get(report = self).service

    @property
    def url_external(self):
        svc = self.service
        return svc.default_proxy.url_public(svc)

    @register.filter
    def authorize(self, user):
        from .project import UserProjectBinding
        return user.is_authenticated and (self.creator == user or len(UserProjectBinding.objects.filter(user = user, project = self.project)) == 1)

    def mark_projectservices_restart(self, reason):
        from .service import ProjectServiceBinding, Service
        n = 0
        for psb in ProjectServiceBinding.objects.filter(project = self.project, service__state__in = [ Service.ST_RUNNING, Service.ST_NEED_RESTART ]):
            if psb.service.mark_restart(reason):
                n += 1
        return n


@receiver(pre_save, sender = Report)
def snapshot_report(sender, instance, **kwargs):
    from kooplex.lib.filesystem import snapshot_report
    is_new = instance.id is None
    if not is_new:
        return
    instance.created_at = now()
    snapshot_report(instance)


@receiver(pre_delete, sender = Report)
def garbage_report(sender, instance, **kwargs):
    from kooplex.lib.filesystem import garbage_report
    garbage_report(instance)



