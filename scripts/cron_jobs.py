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

FROM_EMAIL = "DPS OS <noreply@digitalprod.com>"


def _create_notification(user, title, message, ntype='System', url=None):
    """Create in-app notification for a user."""
    try:
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=ntype,
            related_url=url or '',
        )
    except Exception as e:
        log.warning(f"Could not create notification for {user.email}: {e}")


# ─── 1. Follow-up reminders ───────────────────────────────────────────────────
def send_followup_reminders():
    log.info("=== Sending follow-up reminders ===")
    today = timezone.localdate()
    followups = FollowUp.objects.filter(
        scheduled_at__date=today,
        status='Pending'
    ).select_related('assigned_to')

    count = 0
    for f in followups:
        if not f.assigned_to or not f.assigned_to.email:
            continue
        subject = f"📅 Follow-up Reminder: {f.title}"
        body = (
            f"Hi {f.assigned_to.full_name},\n\n"
            f"You have a follow-up scheduled for TODAY:\n\n"
            f"  Title    : {f.title}\n"
            f"  Type     : {f.follow_up_type}\n"
            f"  Time     : {f.scheduled_at.strftime('%I:%M %p')}\n"
            f"  Related  : {f.related_to_type}\n\n"
            f"Log in to DPS OS to mark it complete: https://dps-os.vercel.app/followups\n\n"
            f"— DPS OS Automated Reminder"
        )
        try:
            send_mail(subject, body, FROM_EMAIL, [f.assigned_to.email], fail_silently=False)
            _create_notification(f.assigned_to, subject, f.title, 'Follow-up', '/followups')
            count += 1
        except Exception as e:
            log.error(f"Failed to email {f.assigned_to.email}: {e}")

    log.info(f"Sent {count}/{followups.count()} follow-up reminder emails.")


# ─── 2. Task due reminders ────────────────────────────────────────────────────
def send_task_reminders():
    log.info("=== Sending task due reminders ===")
    today = timezone.localdate()
    tasks = Task.objects.filter(
        due_date__date=today,
        status__in=['Todo', 'In Progress', 'In Review', 'Blocked']
    ).select_related('assigned_to', 'project')

    count = 0
    for t in tasks:
        if not t.assigned_to or not t.assigned_to.email:
            continue
        project_name = t.project.name if t.project else 'Standalone Task'
        subject = f"⚠️ Task Due Today: {t.title}"
        body = (
            f"Hi {t.assigned_to.full_name},\n\n"
            f"Your task is due TODAY:\n\n"
            f"  Task     : {t.title}\n"
            f"  Project  : {project_name}\n"
            f"  Priority : {t.priority}\n"
            f"  Status   : {t.status}\n\n"
            f"Log in to DPS OS to update it: https://dps-os.vercel.app/tasks\n\n"
            f"— DPS OS Automated Reminder"
        )
        try:
            send_mail(subject, body, FROM_EMAIL, [t.assigned_to.email], fail_silently=False)
            _create_notification(t.assigned_to, subject, t.title, 'Task', '/tasks')
            count += 1
        except Exception as e:
            log.error(f"Failed to email {t.assigned_to.email}: {e}")

    log.info(f"Sent {count}/{tasks.count()} task reminder emails.")


# ─── 3. Expiry alerts (domains, SSL, hosting) ─────────────────────────────────
def check_expiries():
    log.info("=== Checking infrastructure expiries ===")
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
    'check_expiries':     check_expiries,
    'weekly_digest':      send_weekly_digest,
    'eod_report':         send_eod_report,
    # Legacy aliases
    'daily_reminders':    lambda: (send_followup_reminders(), send_task_reminders()),
}

if __name__ == '__main__':
    job_name = sys.argv[1] if len(sys.argv) > 1 else 'followup_reminders'
    if job_name not in JOBS:
        log.error(f"Unknown job: '{job_name}'. Available: {', '.join(JOBS.keys())}")
        sys.exit(1)
    log.info(f"Running job: {job_name}")
    JOBS[job_name]()
    log.info(f"Job '{job_name}' completed.")
