#!/usr/bin/env python
"""
DPS OS — Cron Jobs
Run specific job: python scripts/cron_jobs.py <job_name>

Jobs:
  followup_reminders   — sends email for today's follow-ups (run at 9:00 AM daily)
  task_reminders       — sends email for today's due tasks  (run at 9:05 AM daily)
  check_expiries       — alerts for expiring domains/SSL/hosting (run at 8:00 AM daily)
  weekly_digest        — weekly summary to admin team       (run Monday 8:00 AM)
"""
import os
import sys
import django
import datetime
import logging

# ─── Django setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.utils import timezone
from django.core.mail import send_mail, mail_admins
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, Count

# ─── Models ───────────────────────────────────────────────────────────────────
from apps.tasks.models import Task
from apps.followups.models import FollowUp
from apps.servers.models import Domain, Hosting, SSLCertificate
from apps.notifications.models import Notification

User = get_user_model()

# ─── Logger ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

from django.conf import settings
FROM_EMAIL = settings.DEFAULT_FROM_EMAIL


def is_email_automation_enabled():
    """Check if admin has enabled or paused global automated emails."""
    try:
        from django.conf import settings as dj_settings
        if getattr(dj_settings, 'EMAIL_AUTOMATION_ENABLED', None) is False:
            return False
        from apps.notifications.models import SystemNotificationSetting
        return bool(SystemNotificationSetting.get_settings().email_automation_enabled)
    except Exception as e:
        log.warning(f"Could not check email automation setting: {e}")
        return False


def _create_notification(user, title, message, ntype='System', url=None):
    """Create one in-app notification. Saving it also sends SMTP and push."""
    try:
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=ntype,
            related_url=url or '',
        )
        return True
    except Exception as e:
        log.warning(f"Could not create notification for {user.email}: {e}")
        return False


def _notify_once(user, kind, title, message, ntype='System', url='/dashboard'):
    """Send at most one reminder of this kind to this person today."""
    from apps.notifications.models import ReminderLog
    today = timezone.localdate()
    _, created = ReminderLog.objects.get_or_create(user=user, kind=kind[:40], sent_on=today)
    if not created:
        return False
    return _create_notification(user, title, message, ntype, url)


# ─── 1. Follow-up reminders ───────────────────────────────────────────────────
def send_followup_reminders():
    log.info("=== Sending follow-up reminders ===")
    if not is_email_automation_enabled():
        log.info("Email automation is turned OFF by admin. Skipping follow-up reminders.")
        return
    today = timezone.localdate()
    followups = FollowUp.objects.filter(
        scheduled_at__date=today,
        status='Pending'
    ).select_related('assigned_to')

    count = 0
    for item in followups:
        person = item.assigned_to
        if not person or not person.email:
            continue
        when = timezone.localtime(item.scheduled_at).strftime('%I:%M %p')
        sent = _notify_once(
            person,
            f'followup-{item.id}',
            f'Follow-up today: {item.title}',
            f'{item.follow_up_type} at {when}. Related to {item.related_to_type}. Open Follow-ups and mark it done.',
            'Follow-up',
            '/followups',
        )
        count += int(sent)
    log.info(f"Sent {count}/{followups.count()} follow-up reminders.")


def send_task_reminders():
    log.info("=== Sending task due reminders ===")
    if not is_email_automation_enabled():
        log.info("Email automation is turned OFF by admin. Skipping task reminders.")
        return
    today = timezone.localdate()
    tasks = Task.objects.filter(
        due_date__date=today,
        status__in=['Todo', 'In Progress', 'In Review', 'Blocked']
    ).select_related('assigned_to', 'project')

    count = 0
    for task in tasks:
        person = task.assigned_to
        if not person or not person.email:
            continue
        project_name = task.project.name if task.project else 'Standalone task'
        sent = _notify_once(
            person,
            f'task-{task.id}',
            f'Task due today: {task.title}',
            f'{project_name}. Priority {task.priority}. Status {task.status}.',
            'Task',
            '/tasks',
        )
        count += int(sent)
    log.info(f"Sent {count}/{tasks.count()} task reminders.")


def send_punch_in_reminders():
    """Morning nudge for anyone who has not punched in and is not on approved leave."""
    from apps.accounts.models import Attendance, LeaveRequest
    log.info("=== Punch-in reminders ===")
    if not is_email_automation_enabled():
        log.info("Email automation is turned OFF by admin. Skipping punch-in reminders.")
        return
    today = timezone.localdate()
    on_leave = set(LeaveRequest.objects.filter(
        status='Approved', start_date__lte=today, end_date__gte=today,
    ).values_list('user_id', flat=True))
    punched = set(Attendance.objects.filter(date=today, check_in__isnull=False).values_list('user_id', flat=True))
    people = User.objects.filter(is_active=True).exclude(id__in=on_leave | punched)
    count = 0
    missing_names = []
    for person in people:
        missing_names.append(person.full_name or person.email)
        if _notify_once(
            person,
            'punch-in',
            'Punch in to start your day',
            'You have not punched in yet. Open DPS and tap Punch in so today’s hours count.',
            'System',
            '/dashboard',
        ):
            count += 1
    hr_people = User.objects.filter(role__in=['hr', 'admin', 'superadmin'], is_active=True)
    if missing_names:
        preview = ', '.join(missing_names[:12])
        extra = f' and {len(missing_names) - 12} more' if len(missing_names) > 12 else ''
        for hr in hr_people:
            _notify_once(
                hr,
                'hr-floor',
                f'{len(missing_names)} people have not punched in',
                preview + extra,
                'System',
                '/people',
            )
    log.info(f"Punch-in reminders sent to {count} people. Missing: {len(missing_names)}.")


def send_punch_out_reminders():
    from apps.accounts.models import Attendance
    log.info("=== Punch-out reminders ===")
    if not is_email_automation_enabled():
        log.info("Email automation is turned OFF by admin. Skipping punch-out reminders.")
        return
    today = timezone.localdate()
    open_rows = Attendance.objects.filter(date=today, check_in__isnull=False, check_out__isnull=True).select_related('user')
    count = 0
    for row in open_rows:
        if _notify_once(
            row.user,
            'punch-out',
            'Remember to punch out',
            'You are still punched in. Punch out before you leave so today’s hours close properly.',
            'System',
            '/dashboard',
        ):
            count += 1
    log.info(f"Punch-out reminders sent to {count} people.")


def send_worklog_reminders():
    from apps.accounts.models import Attendance, DailyWorkLog
    log.info("=== Work log reminders ===")
    if not is_email_automation_enabled():
        log.info("Email automation is turned OFF by admin. Skipping work log reminders.")
        return
    today = timezone.localdate()
    logged = set(DailyWorkLog.objects.filter(date=today).values_list('user_id', flat=True))
    rows = Attendance.objects.filter(date=today).exclude(user_id__in=logged).select_related('user')
    count = 0
    for row in rows:
        if _notify_once(
            row.user,
            'work-log',
            'Write today’s work log',
            'You punched in today and have not written a work log yet. Add it before the day closes.',
            'System',
            '/team',
        ):
            count += 1
    log.info(f"Work log reminders sent to {count} people.")


def send_collection_reminders():
    from apps.finance.models import Invoice
    log.info("=== Collection reminders ===")
    if not is_email_automation_enabled():
        log.info("Email automation is turned OFF by admin. Skipping collection reminders.")
        return
    today = timezone.localdate()
    overdue_qs = Invoice.objects.filter(status='Overdue').select_related('client')
    overdue_count = overdue_qs.count()
    overdue = list(overdue_qs[:12])
    if overdue_count == 0:
        log.info("No overdue invoices.")
        return
    names = ', '.join(f"{row.invoice_number} ({row.client.company_name})" for row in overdue)
    recipients = User.objects.filter(role__in=['finance', 'admin', 'superadmin'], is_active=True)
    count = 0
    for person in recipients:
        if _notify_once(
            person,
            'collections',
            f'{overdue_count} invoices need a chase',
            names,
            'Invoice',
            '/finance',
        ):
            count += 1
    log.info(f"Collection reminders sent to {count} people.")


def morning():
    if not is_email_automation_enabled():
        log.warning("NOTE: Email automation is turned OFF by admin. Skipping all morning reminders.")
        return
    send_punch_in_reminders()
    send_followup_reminders()
    send_task_reminders()
    send_collection_reminders()


def evening():
    if not is_email_automation_enabled():
        log.warning("NOTE: Email automation is turned OFF by admin. Skipping all evening reminders.")
        return
    send_punch_out_reminders()
    send_worklog_reminders()


# ─── 3. Expiry alerts (domains, SSL, hosting) ─────────────────────────────────
def check_expiries():
    log.info("=== Checking infrastructure expiries ===")
    if not is_email_automation_enabled():
        log.warning("NOTE: Email automation is turned OFF by admin. Skipping expiry email alerts.")
        return
    today = timezone.localdate()
    admin_emails = list(User.objects.filter(role__in=['superadmin', 'admin'], is_active=True).values_list('email', flat=True))

    # Domains — 30 days warning
    domains = Domain.objects.filter(expiry_date__range=(today, today + datetime.timedelta(days=30)))
    for d in domains:
        days = (d.expiry_date - today).days
        msg = f"⚠️ Domain '{d.domain_name}' expires in {days} day(s) on {d.expiry_date}."
        log.warning(msg)
        if admin_emails:
            send_mail(f"Domain Expiry Alert: {d.domain_name}", msg, FROM_EMAIL, admin_emails, fail_silently=True)

    # SSL Certs — 14 days warning
    certs = SSLCertificate.objects.filter(expiry_date__range=(today, today + datetime.timedelta(days=14)))
    for c in certs:
        days = (c.expiry_date - today).days
        msg = f"🔒 SSL for '{c.domain.domain_name}' expires in {days} day(s) on {c.expiry_date}."
        log.warning(msg)
        if admin_emails:
            send_mail(f"SSL Expiry Alert: {c.domain.domain_name}", msg, FROM_EMAIL, admin_emails, fail_silently=True)

    # Hosting — 7 days warning
    hostings = Hosting.objects.filter(renewal_date__range=(today, today + datetime.timedelta(days=7)))
    for h in hostings:
        days = (h.renewal_date - today).days
        msg = f"🖥️ Hosting for '{h.server_name}' renews in {days} day(s) on {h.renewal_date}."
        log.warning(msg)
        if admin_emails:
            send_mail(f"Hosting Renewal: {h.server_name}", msg, FROM_EMAIL, admin_emails, fail_silently=True)

    log.info(f"Expiry check done. Domains: {domains.count()}, SSL: {certs.count()}, Hosting: {hostings.count()} alerts.")


# ─── 4. Weekly digest ─────────────────────────────────────────────────────────
def send_weekly_digest():
    log.info("=== Sending weekly digest ===")
    if not is_email_automation_enabled():
        log.warning("NOTE: Email automation is turned OFF by admin. Skipping weekly digest email.")
        return
    from django.utils import timezone as tz
    now = tz.now()
    week_ago = now - datetime.timedelta(days=7)

    from apps.leads.models import Lead
    from apps.projects.models import Project

    try:
        from apps.finance.models import Invoice, Expense
        revenue = Invoice.objects.filter(invoice_date__gte=week_ago, status='Paid').aggregate(t=Sum('total_amount'))['t'] or 0
        expenses = Expense.objects.filter(expense_date__gte=week_ago).aggregate(t=Sum('amount'))['t'] or 0
    except Exception:
        revenue = expenses = 0

    new_leads = Lead.objects.filter(created_at__gte=week_ago).count()
    won_leads  = Lead.objects.filter(status='Won', updated_at__gte=week_ago).count()
    tasks_done = Task.objects.filter(status='Done', completed_at__gte=week_ago).count()
    overdue_tasks = Task.objects.filter(
        ~Q(status__in=['Done', 'Cancelled']),
        due_date__lt=now
    ).count()
    active_projects = Project.objects.filter(status__in=['Planning', 'UI Design', 'Development', 'Testing']).count()

    subject = f"📊 DPS OS Weekly Digest — Week ending {now.strftime('%b %d, %Y')}"
    body = f"""
DPS OS — Weekly Team Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 SALES & LEADS
  New Leads This Week  : {new_leads}
  Leads Won            : {won_leads}

📁 PROJECTS & TASKS
  Active Projects      : {active_projects}
  Tasks Completed      : {tasks_done}
  Overdue Tasks        : {overdue_tasks}

💰 FINANCE (WEEK)
  Revenue Collected    : ${revenue:,.2f}
  Expenses             : ${expenses:,.2f}
  Net                  : ${revenue - expenses:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Login to DPS OS: https://dps-os.vercel.app/dashboard
— DPS OS Automated Weekly Report
"""
    admin_emails = list(User.objects.filter(role__in=['superadmin', 'admin'], is_active=True).values_list('email', flat=True))
    if admin_emails:
        try:
            send_mail(subject, body, FROM_EMAIL, admin_emails, fail_silently=False)
            log.info(f"Weekly digest sent to: {', '.join(admin_emails)}")
        except Exception as e:
            log.error(f"Failed to send weekly digest: {e}")


def send_eod_report():
    log.info("=== Generating and Sending End of Day (EOD) Report ===")
    if not is_email_automation_enabled():
        log.warning("NOTE: Email automation is turned OFF by admin. Skipping EOD report email.")
        return
    today = timezone.localdate()
    
    # 1. Fetch Attendance for Today
    from apps.accounts.models import Attendance, DailyWorkLog
    attendances = Attendance.objects.filter(date=today).select_related('user')
    attendance_lines = []
    for a in attendances:
        check_out_str = a.check_out.strftime('%I:%M %p') if a.check_out else 'Still checked in'
        duration_str = f"{a.duration_hours}h" if a.duration_hours else '—'
        attendance_lines.append(
            f" - {a.user.full_name or a.user.email}: Status: {a.status} | Checked In: {a.check_in.strftime('%I:%M %p')} | Checked Out: {check_out_str} | Duration: {duration_str}"
        )
    if not attendance_lines:
        attendance_lines.append(" - No attendance recorded today.")

    # 2. Fetch Daily Work Logs for Today
    worklogs = DailyWorkLog.objects.filter(date=today).select_related('user')
    worklog_sections = []
    for wl in worklogs:
        tasks_list = wl.tasks_completed
        tasks_str = ", ".join([str(t) for t in tasks_list]) if tasks_list else "None specified"
        blockers_str = wl.blockers if wl.blockers else "None reported"
        worklog_sections.append(
            f"🧑 {wl.user.full_name or wl.user.email} (Department: {wl.user.department or '—'})\n"
            f"   Work details:\n"
            f"   {wl.log_text}\n"
            f"   Tasks Completed: {tasks_str}\n"
            f"   Blockers: {blockers_str}\n"
        )
    if not worklog_sections:
        worklog_sections.append(" - No daily work logs submitted today.")

    # 3. Fetch Completed Tasks Today
    tasks_completed_today = Task.objects.filter(status='Done', completed_at__date=today).select_related('assigned_to', 'project')
    task_lines = []
    for t in tasks_completed_today:
        proj_str = t.project.name if t.project else 'General'
        assignee_str = t.assigned_to.full_name if t.assigned_to else 'Unassigned'
        task_lines.append(f" - [{proj_str}] {t.title} (Completed by: {assignee_str})")
    if not task_lines:
        task_lines.append(" - No tasks completed today.")

    # 4. Fetch New Leads Created Today
    from apps.leads.models import Lead
    new_leads = Lead.objects.filter(created_at__date=today)
    lead_lines = []
    for l in new_leads:
        val_str = f"${l.estimated_value}" if l.estimated_value else "—"
        lead_lines.append(f" - {l.company_name} (Contact: {l.contact_person} | Source: {l.lead_source} | Est. Value: {val_str})")
    if not lead_lines:
        lead_lines.append(" - No new leads created today.")

    # Get admin emails
    admin_emails = list(User.objects.filter(role__in=['superadmin', 'admin'], is_active=True).values_list('email', flat=True))
    if not admin_emails:
        log.warning("No admins found to receive EOD report.")
        return

    subject = f"🔔 DPS OS End of Day (EOD) Summary — {today.strftime('%b %d, %Y')}"
    body = (
        f"DPS OS — End of Day (EOD) Summary Report\n"
        f"Date: {today.strftime('%A, %b %d, %Y')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏰ TODAY'S ATTENDANCE SUMMARY\n"
        + "\n".join(attendance_lines) + "\n\n"
        f"📝 SUBMITTED WORK LOGS\n"
        + "\n".join(worklog_sections) + "\n\n"
        f"✅ TASKS COMPLETED TODAY\n"
        + "\n".join(task_lines) + "\n\n"
        f"🔥 NEW LEADS ADDED TODAY\n"
        + "\n".join(lead_lines) + "\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Login to DPS OS to manage: https://dps-os.vercel.app/\n"
        f"— Automated EOD Report System"
    )

    try:
        send_mail(subject, body, FROM_EMAIL, admin_emails, fail_silently=False)
        log.info(f"EOD report sent successfully to: {', '.join(admin_emails)}")
    except Exception as e:
        log.error(f"Failed to send EOD report: {e}")


# ─── Entry point ──────────────────────────────────────────────────────────────
JOBS = {
    'followup_reminders': send_followup_reminders,
    'task_reminders':     send_task_reminders,
    'punch_in':           send_punch_in_reminders,
    'punch_out':          send_punch_out_reminders,
    'work_logs':          send_worklog_reminders,
    'collections':        send_collection_reminders,
    'morning':            morning,
    'evening':            evening,
    'check_expiries':     check_expiries,
    'weekly_digest':      send_weekly_digest,
    'eod_report':         send_eod_report,
    'daily_reminders':    morning,
}

if __name__ == '__main__':
    job_name = sys.argv[1] if len(sys.argv) > 1 else 'followup_reminders'
    if job_name not in JOBS:
        log.error(f"Unknown job: '{job_name}'. Available: {', '.join(JOBS.keys())}")
        sys.exit(1)
    log.info(f"Running job: {job_name}")
    JOBS[job_name]()
    log.info(f"Job '{job_name}' completed.")
