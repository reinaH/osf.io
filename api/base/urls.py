from django.conf import settings
from django.conf.urls import include, url, patterns
from django.conf.urls.static import static
from settings import API_BASE

from . import views

base_pattern = '^{}'.format(API_BASE)

urlpatterns = [
    ### API ###
    url(base_pattern,
        include(patterns('',
                         url(r'^$', views.root, name='root'),
                         url(r'^applications/', include('api.applications.urls', namespace='applications')),
                         url(r'^nodes/', include('api.nodes.urls', namespace='nodes')),
                         url(r'^registrations/', include('api.registrations.urls', namespace='registrations')),
                         url(r'^users/', include('api.users.urls', namespace='users')),
                         url(r'^files/', include('api.files.urls', namespace='files')),
                         url(r'^docs/', include('rest_framework_swagger.urls')),
                         ))
        )
]

urlpatterns += static('/static/', document_root=settings.STATIC_ROOT)

handler404 = views.error_404
