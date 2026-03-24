from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class WorkingView(APIView):
    """
    Placeholder view for the working app.
    Replace with your actual logic.
    """
    def get(self, request):
        return Response({'message': 'working app is ready'}, status=status.HTTP_200_OK)
