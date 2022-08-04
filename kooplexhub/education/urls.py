from django.urls import path, re_path

from . import views

app_name = 'education'

urlpatterns = [
    path('teaching/', views.TeacherCourseBindingListView.as_view(), name = 'teacher'),
    path('course/', views.StudentCourseBindingListView.as_view(), name = 'student'),
    path('assignment_teachers_view/', views.assignment_teacher, name = 'assignment_teacher'), # just a dispatcher
    path('assignment_new/', views.assignment_new, name = 'assignment_new'),
    path('assignment_configure/', views.assignment_configure, name = 'assignment_configure'),
    path('assignment_handle/', views.assignment_handle, name = 'assignment_handle'),
    path('assignment_handle_mass/', views.assignment_handle_mass, name = 'assignment_handle_mass'),
    path('assignment_summary/', views.assignment_summary, name = 'assignment_summary'),

    path('newassignment/', views.newassignment, name = 'newassignment'), #FIXME
    path('configureassignment/', views.configureassignment, name = 'configureassignment'), #FIXME:
    path('assignment_mass/', views.handle_mass, name = 'handle_mass'), #FIXME
    path('assignment_mass_many/', views.handle_mass_many, name = 'handle_mass_many'),
    re_path('assignment_students_view/(?P<usercoursebinding_id>\d+)?/?$', views.assignment_student, name = 'assignment_student'),
    path('handleassigment/', views.handleassignment, name = 'handleassigment'),
    path('submitform/', views.submitform_submit, name = 'submit'),
    re_path('configure/(?P<usercoursebinding_id>\d+)/?$', views.configure, name = 'configure'),
    re_path('configure_save/(?P<usercoursebinding_id>\d+)/?$', views.configure_save, name = 'configure_save'),
    re_path('addcontainer/(?P<usercoursebinding_id>\d+)/?$', views.addcontainer, name = 'autoaddcontainer'),
]
