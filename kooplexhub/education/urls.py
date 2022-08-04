from django.urls import path, re_path

from . import views

app_name = 'education'

urlpatterns = [
    path('teaching/', views.TeacherCourseBindingListView.as_view(), name = 'teacher'),
    path('course/', views.StudentCourseBindingListView.as_view(), name = 'student'),
    path('assignment_teachers_view/', views.assignment_teacher, name = 'assignment_teacher'), # just a dispatcher
    path('assignment_new/', views.assignment_new, name = 'assignment_new'),
    path('assignment_new_save/', views.assignment_new_, name = 'assignment_new_save'),
    path('assignment_configure/', views.assignment_configure, name = 'assignment_configure'),
    path('assignment_configure_save/', views.assignment_configure_, name = 'assignment_configure_save'),
    path('assignment_handler/', views.assignment_handler, name = 'assignment_handler'),
    path('assignment_individual_handle/', views.assignment_individual_handle, name = 'assignment_individual_handle'),
    path('assignment_mass/', views.assignment_mass, name = 'assignment_mass'),
    path('assignment_mass_handle/', views.assignment_mass_, name = 'assignment_mass_handle'),
    path('assignment_mass_handle__/', views.assignment_mass___, name = 'assignment_mass_handle___'), #FIXME
    path('assignment_summary/', views.assignment_summary, name = 'assignment_summary'),

    re_path('assignment/(?P<usercoursebinding_id>\d+)?/?$', views.assignment_student, name = 'assignment_student'),
    path('submitform/', views.submitform_submit, name = 'submit'),
    re_path('configure/(?P<usercoursebinding_id>\d+)/?$', views.configure, name = 'configure'),
    re_path('configure_save/(?P<usercoursebinding_id>\d+)/?$', views.configure_save, name = 'configure_save'),
    re_path('addcontainer/(?P<usercoursebinding_id>\d+)/?$', views.addcontainer, name = 'autoaddcontainer'),
]
