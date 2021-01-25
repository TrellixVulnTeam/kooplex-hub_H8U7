import os
import pwgen
import logging
import unidecode

from django.db import models
from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User

from kooplex.settings import KOOPLEX
from kooplex.lib.filesystem import Dirname
from kooplex.lib import sudo

logger = logging.getLogger(__name__)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)
    bio = models.TextField(max_length = 500, blank = True)
    location = models.CharField(max_length = 30, blank = True)
    userid = models.IntegerField(null = False)
    token = models.CharField(max_length = 64, null = True)
    can_createproject = models.BooleanField(default = True) 
    can_createimage = models.BooleanField(default = False) 

    @property
    def name(self):
        return '{} {}'.format(self.user.first_name, self.user.last_name)

    @property
    def username(self):
        return '{}'.format(self.user.username)

    @property
    def name_and_username(self):
        return f'{self.name} ({self.username})'

    @property
    def safename(self):
        return "%s_%s" % (unidecode.unidecode(self.user.last_name), unidecode.unidecode(self.user.first_name).replace(' ', ''))

    @property
    def everybodyelse(self):
        return Profile.objects.filter(~models.Q(id = self.id) & ~models.Q(user__is_superuser = True))

    def everybodyelse_like(self, pattern):
        return Profile.objects.filter(~models.Q(id = self.id) & ~models.Q(user__is_superuser = True) & (models.Q(user__username__icontains = pattern) | models.Q(user__first_name__icontains = pattern) | models.Q(user__last_name__icontains = pattern)))

    @property
    def projectbindings(self):
        from .project import UserProjectBinding
        for binding in UserProjectBinding.objects.filter(user = self.user):
            yield binding

    @property
    def number_of_hidden_projects(self):
        return len(list(filter(lambda x: x.is_hidden, self.projectbindings)))

    @property
    def containers(self):
        from .service import Service
        for svc in Service.objects.filter(user = self.user):
             yield svc

    @property
    def reports(self):
        from .report import Report
        from hub.forms import T_REPORTS, T_REPORTS_DEL
        reports_shown = set()
        for report in Report.objects.all():#FIXME: filter those you can see
             if report in reports_shown:
                 continue
             g = report.groupby()
             T = T_REPORTS_DEL(g) if self.user == report.creator else T_REPORTS(g)
             yield report.latest, T, report.subcategory_name
             reports_shown.update(set(g))

    def usercoursebindings(self, **kw):
        from .course import UserCourseBinding
        for binding in UserCourseBinding.objects.filter(user = self.user, **kw):
            yield binding

    @property
    def is_teacher(self):
        return len(list(self.usercoursebindings(is_teacher = True))) > 0

    def courses_taught(self):
        return set([ binding.course for binding in self.usercoursebindings(is_teacher = True) ])

    @property
    def is_student(self):
        return len(list(self.usercoursebindings(is_teacher = False))) > 0

    def courses_attend(self):
        return set([ binding.course for binding in self.usercoursebindings(is_teacher = False) ])

    def is_coursecodeteacher(self, coursecode):
        from .course import UserCourseCodeBinding
        try:
            UserCourseCodeBinding.objects.get(user = self.user, coursecode = coursecode, is_teacher = True)
            return True
        except UserCourseCodeBinding.DoesNotExist:
            return False

    @property
    def courseprojects_attended(self): #FIXME
        duplicate = set()
        for coursebinding in self.coursebindings:
            if not coursebinding.is_teacher:
                if coursebinding.course.project in duplicate:
                    continue
                yield coursebinding.course.project
                duplicate.add(coursebinding.course.project)

    def projects_reportprepare(self):
        for b in self.projectbindings:
            yield (b.project.id, b.project.uniquename)

    @sudo
    def files_reportprepare(self):
        tree = {}
        for b in self.projectbindings:
            report_dir = Dirname.reportprepare(b.project)
            sub_tree = {}
            for d in list(filter(lambda d: not d.startswith('.') and os.path.isdir(os.path.join(report_dir, d)), os.listdir(report_dir))):
                files = list(filter(lambda f: f.endswith('.ipynb') or f.endswith('.html') or f.endswith('.py') or f.endswith('.R') or f.endswith('.r'), os.listdir( os.path.join(report_dir, d) )))
                if len(files):
                    sub_tree[d] = files
            if len(sub_tree):
                tree[b.project] = sub_tree
        return tree

    @property
    def functional_volumes(self):
        from .volume import Volume
        for volume in Volume.filter(Volume.FUNCTIONAL):
            yield volume

    @property
    def storage_volumes(self):
        from .volume import Volume
        for volume in Volume.filter(Volume.STORAGE, user = self.user):
            yield volume

    @property
    def vctokens(self):
        from .versioncontrol import VCToken
        for t in VCToken.objects.filter(user = self.user):
            yield t

    @property
    def fstokens(self):
        from .filesync import FSToken
        for t in FSToken.objects.filter(user = self.user):
            yield t


@receiver(post_save, sender = User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        logger.info("New user %s" % instance)
        last_uid = Profile.objects.all().aggregate(models.Max('userid'))['userid__max']
        uid = KOOPLEX.get('min_userid', 1000) if last_uid is None else last_uid + 1
        token = pwgen.pwgen(64)
        Profile.objects.create(user = instance, userid = uid, token = token)


@receiver(post_save, sender = User)
def create_user_home(sender, instance, created, **kwargs):
    from kooplex.lib.filesystem import mkdir_home
    if created:
        try:
            mkdir_home(instance)
        except Exception as e:
            logger.error("Failed to create home for %s -- %s" % (instance, e))


@receiver(pre_delete, sender = User)
def garbage_user_home(sender, instance, **kwargs):
    from kooplex.lib.filesystem import garbagedir_home
    garbagedir_home(instance)


@receiver(post_save, sender = User)
def ldap_create_user(sender, instance, created, **kwargs):
    from kooplex.lib.ldap import Ldap
    regenerate = False
    try:
        ldap = Ldap()
        response = ldap.get_user(instance)
        uidnumber = response.get('attributes', {}).get('uidNumber')
        if uidnumber != instance.profile.userid:
            ldap.removeuser(instance)
            regenerate = True
    except Exception as e:
        logger.error("Failed to get ldap entry for %s -- %s" % (instance, e))
    if not created or regenerate:
        try:
            ldap.adduser(instance)
        except Exception as e:
            logger.error("Failed to create ldap entry for %s -- %s" % (instance, e))


@receiver(post_delete, sender = User)
def ldap_delete_user(sender, instance, **kwargs):
    from kooplex.lib.ldap import Ldap
    try:
        Ldap().removeuser(instance)
    except Exception as e:
        logger.error("Failed to remove ldap entry for %s -- %s" % (instance, e))


