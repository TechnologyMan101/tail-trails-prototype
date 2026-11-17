from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"), path("healthz", views.healthz, name="healthz"),
    path("login", views.sign_in, name="login"), path("logout", views.sign_out, name="logout"),
    path("animals", views.animals, name="animals"), path("animals/new", views.animal_edit, name="animal_new"),
    path("animals/<int:pk>", views.animal_profile, name="animal_profile"), path("animals/<int:pk>/edit", views.animal_edit, name="animal_edit"),
    path("animals/<int:pk>/submit", views.submit_update, name="submit_update"),
    path('animals/<int:pk>/delete', views.animal_delete, name='animal_delete'),
    path('hours/<int:pk>/delete', views.hour_delete, name='hour_delete'),
    path("animals/<int:pk>/confirm-euthanized", views.animal_euthanize, name="animal_euthanize"),
    path("submissions", views.submissions, name="submissions"), path("submissions/<int:pk>/<str:action>", views.review_submission, name="review_submission"),
    path("hours", views.volunteer_hours, name="volunteer_hours"), path("users", views.manage_users, name="users"),
    path("users/<int:pk>/toggle", views.user_toggle, name="user_toggle"), path("organization", views.organization, name="organization"),
    path("organization/preview/<str:kind>", views.branding_preview, name="branding_preview"),
    path("photo-batches/<uuid:batch_id>", views.photo_batch_crop, name="photo_batch_crop"),
    path("photo-batches/<uuid:batch_id>/photos/<int:photo_id>/preview", views.photo_batch_preview, name="photo_batch_preview"),
    path("photo-batches/<uuid:batch_id>/cancel", views.photo_batch_cancel, name="photo_batch_cancel"),
    path("system", views.system_information, name="system_information"),
    path("system/stream", views.system_information_stream, name="system_information_stream"),
    path("account", views.account, name="account"),
    path("media/<path:path>", views.media_file, name="media_file"),
    path("backend/photos/<str:kind>/<int:pk>/original", views.original_photo, name="original_photo"),
]

