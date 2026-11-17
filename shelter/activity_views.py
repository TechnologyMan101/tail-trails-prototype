import csv
import json
from datetime import timedelta, datetime, time
from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from .views import roles
from .models import AuditEvent, Animal
from .audit import record


class AuditFilters(forms.Form):
    actor = forms.CharField(required=False, label='Account name or ID')
    action = forms.CharField(required=False)
    target = forms.CharField(required=False, label='Record name or ID')
    animal = forms.CharField(required=False, label='Animal ID or name')
    animal_id = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    category = forms.ChoiceField(required=False, choices=[('', 'All categories'), *[(s, s.title()) for s in ('routine','critical','access','operational')]])
    outcome = forms.ChoiceField(required=False, choices=[('', 'All outcomes'), ('success','Success'), ('failure','Failure')])
    since = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}))
    until = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}))


@roles('Administrator')
def activity_log(request):
    form = AuditFilters(request.GET)
    qs = AuditEvent.objects.all()
    if form.is_valid():
        data = form.cleaned_data
        if data['actor']:
            match = Q(actor_name__icontains=data['actor'])
            if data['actor'].isdigit(): match |= Q(actor_id_snapshot=int(data['actor']))
            qs = qs.filter(match)
        if data['target']: qs = qs.filter(Q(target_label__icontains=data['target']) | Q(target_id=data['target']))
        if data['animal']:
            term = data['animal']
            current = Animal.objects.filter(Q(name__icontains=term) | Q(animal_id__icontains=term)).values('pk')
            historical = AuditEvent.objects.filter(target_type='animal', target_label__icontains=term).values('animal_id_snapshot')
            qs = qs.filter(Q(animal_id_snapshot__in=current) | Q(animal_id_snapshot__in=historical))
        for field in ('category','outcome'):
            if data[field]: qs = qs.filter(**{field:data[field]})
        if data['action']: qs = qs.filter(action__icontains=data['action'])
        if data['animal_id']: qs = qs.filter(animal_id_snapshot=data['animal_id'])
        if data['since']: qs = qs.filter(created_at__gte=timezone.make_aware(datetime.combine(data['since'], time.min)))
        if data['until']: qs = qs.filter(created_at__lt=timezone.make_aware(datetime.combine(data['until']+timedelta(days=1), time.min)))
    else: qs = qs.none()
    export_error = ''
    if request.GET.get('format') == 'csv' and form.is_valid():
        rows = list(qs[:10001])
        if len(rows) > 10000: export_error = 'Export limited to 10,000 events. Narrow the date range or filters.'
        else:
            record('critical', 'audit.exported', changes={'rows':len(rows)})
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="tail-trails-activity.csv"'
            writer = csv.writer(response)
            writer.writerow(['UTC time','Actor','Role','Action','Category','Outcome','Record','Record ID','Animal ID','Request ID','Changes'])
            for row in rows:
                values = [row.created_at.isoformat(),row.actor_name,row.actor_role,row.action,row.category,row.outcome,row.target_label,row.target_id,row.animal_id_snapshot or '',row.request_id,json.dumps(row.changes)]
                writer.writerow(["'"+str(value) if str(value).startswith(('=','+','-','@','\t','\r','\n')) else value for value in values])
            return response
    page = Paginator(qs, 50).get_page(request.GET.get('page'))
    query = request.GET.copy(); query.pop('page',None);query.pop('format',None)
    return render(request, 'activity_log.html', {'filter_form':form,'page':page,'query':query.urlencode(),'retention':settings.AUDIT_RETENTION_DAYS,'cleanup_minutes':settings.AUDIT_CLEANUP_INTERVAL_MINUTES,'last_cleanup':AuditEvent.objects.filter(action='audit.retention.pruned').first(),'export_error':export_error})
