from rest_framework import generics, mixins, permissions, status
from rest_framework.response import Response

from .serializers import SetAvatarSerializer


class AvatarViewSet(mixins.UpdateModelMixin, generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, *args, **kwargs):
        serializer = SetAvatarSerializer(
            instance=request.user, data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'avatar': request.user.avatar.url if request.user.avatar else None
        })

    def delete(self, request, *args, **kwargs):
        """Удаление аватара."""
        user = request.user
        if user.avatar:
            user.avatar.delete(save=True)
        user.avatar = None
        user.save(update_fields=['avatar'])
        return Response(status=status.HTTP_204_NO_CONTENT)
