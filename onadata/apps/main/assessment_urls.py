
from.assessment_views import fetch_form_submissions,OAuthFormSubmissionsAPIView
from django.urls import re_path

urlpatterns = [
    #Display form
re_path(
    r"^form/(?P<form_id>\d+)/$",
    fetch_form_submissions,
    name="fetch_form_submissions",
),
# OAuth-protected API endpoint for fetching Ona form submissions
re_path(
    r"^api/assessment/form/(?P<form_id>\d+)/$",
    OAuthFormSubmissionsAPIView.as_view(),
    name="oauth_form_submissions_api",
),

]

