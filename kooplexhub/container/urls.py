from django.urls import path, re_path

from . import views

app_name = 'container'

urlpatterns = [
    path('new/', views.NewContainerView.as_view(), name = 'new'),
    re_path('^delete/(?P<container_id>\d+)/(?P<next_page>\w+:?\w*)/?', views.destroy, name = 'destroy'),
    path('list/', views.ContainerListView.as_view(), name = 'list'),
    re_path('^configure/(?P<container_id>\d+)/?', views.configure, name = 'configure'),

    re_path('^start/(?P<container_id>\d+)/(?P<next_page>\w+:?\w*)/?', views.start, name = 'start'),
    re_path('^stop/(?P<container_id>\d+)/(?P<next_page>\w+:?\w*)/?', views.stop, name = 'stop'),
    re_path('^restart/(?P<container_id>\d+)/(?P<next_page>\w+:?\w*)/?', views.restart, name = 'restart'),
    re_path('^info/(?P<container_id>\d+)/?', views.refresh, name = 'refreshlogs'),
    re_path('^open/(?P<container_id>\d+)/(?P<next_page>\w+:?\w*)/(?P<shown>.*)?/?', views.open, name = 'open'),

    path('attachments/', views.AttachmentListView.as_view(), name = 'list_attachments'),
    path('new_attachment/', views.NewAttachmentView.as_view(), name = 'new_attachment'),
]
