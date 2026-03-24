from django.urls import path
from live.views import MatchStatement, DownloadFileView

urlpatterns = [
    path('', MatchStatement.as_view(), name='format'),
    path('download-file/', DownloadFileView.as_view(), name='download_file'),
]
