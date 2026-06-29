from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView, VerifyOTPView, UserProfileView,
    ChangePasswordView, LogoutView, RequestPasswordOTPView, ChangePasswordOTPView
)

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('me/', UserProfileView.as_view(), name='user_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('profile/request-otp/', RequestPasswordOTPView.as_view(), name='request_password_otp'),
    path('profile/change-password-otp/', ChangePasswordOTPView.as_view(), name='change_password_otp'),
]
