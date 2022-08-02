import os
import re
import logging

from django.db import models
from django.contrib.auth.models import User
from django.template.defaulttags import register

from hub.lib import dirname
from ..models import Course, UserCourseBinding

logger = logging.getLogger(__name__)


class Assignment(models.Model):
    name = models.CharField(max_length = 32, null = False)
    course = models.ForeignKey(Course, null = False, on_delete = models.CASCADE)
    creator = models.ForeignKey(User, null = False, on_delete = models.CASCADE)
    description = models.TextField(max_length = 500)
    folder = models.CharField(max_length = 32, null = False)
    created_at = models.DateTimeField(auto_now_add = True)
    valid_from = models.DateTimeField(null = True, blank = True)
    expires_at = models.DateTimeField(null = True, blank = True)
    remove_collected = models.BooleanField(default = False)
    max_size = models.IntegerField(default = None, null = True) 
    filename = models.CharField(max_length = 256, null = False, unique = True)

    class Meta:
        unique_together = [['course', 'folder']]

    def __str__(self):
        return f"Assignment {self.name} (course {self.course.name}@{self.creator.username})"

    @property
    def safename(self):
        return re.sub(r'[\.\ ]', '', self.name)

    @property
    def snapshot(self):
        return os.path.join(dirname.course_assignment_snapshot(self.course), 'assignment-snapshot-%s.%d.tar.gz' % (self.safename, self.created_at.timestamp()))

class UserAssignmentBinding(models.Model):
    ST_QUEUED = 'qed'
    ST_WORKINPROGRESS = 'wip'
    ST_SUBMITTED = 'sub'
    ST_COLLECTED = 'col'
    ST_CORRECTED = 'cor'
    ST_READY = 'rdy'
    ST_LOOKUP = {
        ST_QUEUED: 'Waiting for handout',
        ST_WORKINPROGRESS: 'Working on assignment',
        ST_SUBMITTED: 'Submitted, waiting for corrections',
        ST_COLLECTED: 'Collected, waiting for corrections',
        ST_CORRECTED: 'Assignment is being corrected',
        ST_READY: 'Assignment is corrected',
    }

    user = models.ForeignKey(User, null = False, on_delete = models.CASCADE)
    assignment = models.ForeignKey(Assignment, null = False, on_delete = models.CASCADE)
    received_at = models.DateTimeField(null = True, default = None, blank = True)
    valid_from = models.DateTimeField(null = True, default = None, blank = True)
    expires_at = models.DateTimeField(null = True, default = None, blank = True)
    state = models.CharField(max_length = 16, choices = ST_LOOKUP.items(), default = ST_QUEUED)
    submitted_at = models.DateTimeField(null = True, default = None, blank = True)
    corrector = models.ForeignKey(User, null = True, related_name = 'corrector', on_delete = models.CASCADE, blank = True)
    corrected_at = models.DateTimeField(null = True, default = None, blank = True)
    score = models.FloatField(null = True, default = None, blank = True)
    feedback_text = models.TextField(null = True, default = None, blank = True)
    submit_count = models.IntegerField(default = 0, null = False)
    correction_count = models.IntegerField(default = 0, null = False)

    class Meta:
        unique_together = [['user', 'assignment']]
        ordering = [ 'assignment__name' ]


    def __str__(self):
        return f'{self.assignment.name} ({self.assignment.course.name})'

    @register.filter
    def state_long(self):
        return ST_LOOKUP[self.state] 

#FIXME:    @staticmethod
#FIXME:    def iter_valid():
#FIXME:        timenow = now()
#FIXME:        for binding in UserAssignmentBinding.objects.filter(state = UserAssignmentBinding.ST_QUEUED):
#FIXME:            if timenow > binding.valid_from:
#FIXME:                yield binding
#FIXME:
#FIXME:    def do_activate(self):
#FIXME:        #FIXME: we may double check state and skip some bindings
#FIXME:        self.state = UserAssignmentBinding.ST_WORKINPROGRESS
#FIXME:        self.received_at = now()
#FIXME:        self.save()
#FIXME:        logger.info(self)
#FIXME:
#FIXME:    @staticmethod
#FIXME:    def iter_expired():
#FIXME:        timenow = now()
#FIXME:        for binding in UserAssignmentBinding.objects.filter(state = UserAssignmentBinding.ST_WORKINPROGRESS):
#FIXME:            if binding.expires_at is None:
#FIXME:                continue
#FIXME:            if timenow > binding.expires_at:
#FIXME:                yield binding
#FIXME:
#FIXME:    def do_collect(self):
#FIXME:        #FIXME: we may double check state and skip some bindings
#FIXME:        self.state = UserAssignmentBinding.ST_COLLECTED
#FIXME:        self.submitted_at = now()
#FIXME:        self.save()
#FIXME:        logger.info(self)
#FIXME:


