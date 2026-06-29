"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/leads/", include("apps.leads.urls")),
    path("api/clients/", include("apps.clients.urls")),
    path("api/projects/", include("apps.projects.urls")),
    path("api/tasks/", include("apps.tasks.urls")),
    path("api/followups/", include("apps.followups.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/finance/", include("apps.finance.urls")),
    path("api/marketing/", include("apps.marketing.urls")),
    path("api/seo/", include("apps.seo.urls")),
    path("api/products/", include("apps.products.urls")),
    path("api/servers/", include("apps.servers.urls")),
    path("api/knowledge/", include("apps.knowledge.urls")),
    path("api/team/", include("apps.accounts.urls_team")),
    path("api/", include("apps.reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

