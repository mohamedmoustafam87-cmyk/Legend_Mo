"""Existing clock slots, same-day catchup, explicit activation, durable dedup.
No external reads on dry-run or before the activation gate. No notification preamble.
"""
import hashlib
import json
import os
import sys
from datetime import datetime
from config import TIMEZONE, REPORT_TIMES, TRADING_WEEKDAYS, EGX_HOLIDAYS

# Preparation commit is inert even if repository variables were already set.
# Change only after final source-grounded recurring-operation scope assessment.
ACTIVATION_APPROVED = False


def due_slot(now):
    if now.tzinfo is None: raise ValueError('Aware time required')
    now = now.astimezone(TIMEZONE)
    if now.weekday() not in TRADING_WEEKDAYS or now.date().isoformat() in EGX_HOLIDAYS:
        return None
    eligible = [(h,m) for h,m in REPORT_TIMES if (now.hour,now.minute)>=(h,m)]
    if not eligible: return None
    h,m = max(eligible)
    return now.date().isoformat()+f'T{h:02d}:{m:02d}'


def content_identity(report):
    messages = report['messages']
    if not messages or any(not isinstance(t,str) or not t or len(t.encode('utf-16-le'))//2>3800 for t in messages):
        raise ValueError('Invalid message bounds')
    # Message content includes price dates, selected holdings/costs and format version.
    # Retrieval time, run IDs and clock slot never create new report identities.
    raw = json.dumps(messages,ensure_ascii=False,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()


def report_dates(report):
    dates = {r['ticker']:r['history_as_of'] for r in report['records']}
    dates.update({r['ticker']+'.CA':r['date'] for r in report['snapshot']['rows'] if r['date']})
    return dates


def execute(now=None, dry_run=False, journal=None, collect=None, enabled=None):
    now = now or datetime.now(TIMEZONE)
    if enabled is None:
        enabled = (ACTIVATION_APPROVED and os.getenv('TELEGRAM_DELIVERY_ENABLED')=='true' and
                   os.getenv('SCHEDULED_DATED_REPORT_ENABLED')=='true')
    if dry_run or not enabled:
        print('Validation only. Activation gated; no source calls or messages.')
        return 'gated'
    slot = due_slot(now)
    if slot is None:
        print('No configured same-day slot due; no external calls.')
        return 'not-due'
    if journal is None:
        from private_journal import PrivateJournal
        journal = PrivateJournal(os.environ['TELEGRAM_TOKEN'].strip(),
            os.environ['GH_TOKEN'].strip(),os.environ['GITHUB_REPOSITORY'])
    journal.load()
    journal.assert_no_ambiguous()
    control = journal.state.setdefault('_scheduled_v1', {'slots':{},'hashes':{},'latest_dates':{}})
    if slot in control['slots']:
        return 'slot-already-checked'
    destination = os.environ['ADMIN_CHAT_ID'].strip()
    destination_hash = hashlib.sha256(destination.encode()).hexdigest()
    if control.get('destination_hash') not in (None,destination_hash):
        raise ValueError('Destination changed; no automatic disclosure')
    control['destination_hash'] = destination_hash
    journal.verify_private(destination)
    # Persist source attempt first. A failed scan waits for the next original slot;
    # repeated cron triggers cannot multiply provider requests at the same slot.
    control['slots'][slot] = 'checking'
    journal.persist()
    if collect is None:
        from scheduled_research import collect_dated_report
        collect = collect_dated_report
    report = collect(now=now)
    identity = content_identity(report)
    dates = report_dates(report)
    prior = control['latest_dates']
    if any(s not in dates or dates[s] < d for s,d in prior.items()):
        control['slots'][slot] = 'source-regressed'; journal.persist()
        return 'source-regressed'
    # Bootstrap is deliberately silent. It prevents resending the already received
    # static session when recurrence is first activated. Next changed data can send.
    if not control['hashes']:
        control['hashes'][identity] = 'baseline'
        control['latest_dates'] = dates
        control['slots'][slot] = 'baseline-only'; journal.persist()
        return 'baseline-only'
    if identity in control['hashes']:
        control['slots'][slot] = 'unchanged'; journal.persist()
        return 'unchanged'
    # One whole-batch claim before ANY send: a crash/timeout anywhere blocks later
    # schedules until receipt reconciliation. No resend of a partially accepted batch.
    key = 'scheduled:'+identity
    journal.state[key] = {'status':'claimed','receipts':[],'slot':slot,
                          'destination_hash':hashlib.sha256(destination.encode()).hexdigest()}
    journal.persist()
    for index,text in enumerate(report['messages']):
        response = journal.telegram('sendMessage',{'chat_id':destination,'text':text})
        result = response.get('result',{})
        if not response.get('ok') or str(result.get('chat',{}).get('id'))!=destination or not result.get('message_id'):
            raise ValueError('Delivery unconfirmed')
        journal.state[key]['receipts'].append({'part':index,'message_id':result['message_id'],'date':result.get('date')})
        journal.persist()
    journal.state[key]['status'] = 'sent'
    control['hashes'][identity] = 'sent'
    for symbol,date in dates.items(): control['latest_dates'][symbol] = max(date,prior.get(symbol,date))
    control['slots'][slot] = 'sent'
    journal.persist()
    print('Dated private batch accepted; receipts encrypted. Content omitted from logs.')
    return 'sent'


if __name__=='__main__':
    try:
        execute(dry_run='--dry-run' in sys.argv)
    except Exception as error:
        # Never expose request URLs, credentials, holdings or report body in logs.
        print('Stopped safely:',type(error).__name__,'. No automatic send retry.')
        sys.exit(1)
