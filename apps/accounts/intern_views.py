from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .access import can_manage_people
from .models import InternProfile, TestReport

User = get_user_model()


def _can_manage(user):
    return user.role in ('superadmin', 'admin', 'hr', 'manager') or can_manage_people(user)


def _person(user):
    profile = getattr(user, 'intern_profile', None)
    return {
        'id': user.id,
        'full_name': user.full_name or user.email,
        'email': user.email,
        'phone': user.phone,
        'role': user.role,
        'location': profile.location if profile else '',
        'focus': profile.focus if profile else 'Tester',
        'is_active': user.is_active,
    }


def _report(row):
    return {
        'id': row.id,
        'title': row.title,
        'area': row.area,
        'detail': row.detail,
        'location': row.location,
        'status': row.status,
        'created_at': row.created_at,
        'author': row.author_id,
        'author_name': row.author.full_name or row.author.email,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def interns(request):
    if request.method == 'POST':
        if not _can_manage(request.user):
            return Response({'detail': 'Only staff who manage people can add a tester login.'}, status=status.HTTP_403_FORBIDDEN)
        email = (request.data.get('email') or '').strip().lower()
        name = (request.data.get('full_name') or '').strip()
        password = request.data.get('password') or ''
        location = (request.data.get('location') or '').strip()
        focus = (request.data.get('focus') or 'Tester').strip() or 'Tester'
        if not email or not name:
            return Response({'detail': 'Name and email are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(password) < 8:
            return Response({'detail': 'Password needs at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email=email).exists():
            return Response({'detail': 'That email already has a login.'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(
            email=email,
            password=password,
            role='intern',
            full_name=name,
            phone=(request.data.get('phone') or '').strip(),
            department=location,
        )
        InternProfile.objects.create(user=user, location=location, focus=focus)
        try:
            send_mail(
                'Your DPS OS tester login',
                (
                    f"Hi {name},\n\n"
                    f"You can sign in to DPS OS on the website and the phone app with the same login.\n\n"
                    f"Email: {email}\n"
                    f"Password: {password}\n\n"
                    f"Website: https://crm.digitalproductsolutions.in/login\n\n"
                    f"Open Interns after you sign in, and file what you tested.\n"
                ),
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,
            )
        except Exception:
            pass
        return Response(_person(user), status=status.HTTP_201_CREATED)

    people = User.objects.filter(role='intern', is_active=True).select_related('intern_profile').order_by('full_name', 'email')
    if not _can_manage(request.user):
        people = people.filter(pk=request.user.pk)
    return Response([_person(row) for row in people])


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def intern_reports(request):
    if request.method == 'POST':
        title = (request.data.get('title') or '').strip()
        detail = (request.data.get('detail') or '').strip()
        if not title or not detail:
            return Response({'detail': 'Say what you tested and what you found.'}, status=status.HTTP_400_BAD_REQUEST)
        row = TestReport.objects.create(
            author=request.user,
            title=title,
            area=(request.data.get('area') or '').strip(),
            detail=detail,
            location=(request.data.get('location') or '').strip(),
        )
        return Response(_report(row), status=status.HTTP_201_CREATED)

    rows = TestReport.objects.select_related('author')
    if not _can_manage(request.user):
        rows = rows.filter(author=request.user)
    return Response([_report(row) for row in rows])


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def intern_report_status(request, pk):
    if not _can_manage(request.user):
        return Response({'detail': 'Only staff can close a report.'}, status=status.HTTP_403_FORBIDDEN)
    row = TestReport.objects.filter(pk=pk).first()
    if not row:
        return Response({'detail': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)
    status_value = request.data.get('status')
    if status_value in ('Open', 'Fixed'):
        row.status = status_value
        row.save(update_fields=['status'])
    return Response(_report(row))
