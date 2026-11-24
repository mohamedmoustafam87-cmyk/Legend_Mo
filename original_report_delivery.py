"""Operational adapter only. Uses owner's original report/analysis unchanged."""
import os,sys,hashlib
from datetime import datetime
from private_journal import PrivateJournal


def main():
    if '--dry-run' in sys.argv:
        import app  # Not used by workflow; use compile checks instead.
        return
    destination=os.environ['ADMIN_CHAT_ID'].strip()
    journal=PrivateJournal(os.environ['TELEGRAM_TOKEN'].strip(),os.environ['GH_TOKEN'],os.environ['GITHUB_REPOSITORY'])
    journal.load();journal.assert_no_ambiguous();journal.verify_private(destination)
    identity='original-report:owner-request-2026-11-24T15:37:02-Cairo'
    if journal.state.get(identity,{}).get('status')=='sent':
        print('Requested original report already sent; skipped.');return
    if identity in journal.state:raise ValueError('Ambiguous original request')
    # Claim BEFORE even computing the requested report, so job retries cannot
    # accidentally fetch/send another whole report after a partial failure.
    journal.state[identity]={'status':'claimed','receipts':[]};journal.persist()
    import scanner,portfolio,report
    dates=set()
    original=scanner.get_stock_data
    cache={}
    def tracked(symbol,mubasher_prices=None):
        if symbol not in cache:
            cache[symbol]=original(symbol,{})
            frame,_=cache[symbol]
            if frame is not None and not frame.empty:dates.add(frame.index[-1].date().isoformat())
        return cache[symbol]
    scanner.get_stock_data=tracked;portfolio.get_stock_data=tracked
    opportunities,ctx=scanner.scan_market(return_context=True)
    holdings=portfolio.analyze_user_portfolio(ctx)
    # EXACT owner's original formatter and sections, not our replacement.
    messages=report.format_scanner_messages(opportunities,ctx)+report.format_portfolio_messages(holdings)
    if not messages or any(len(t.encode('utf-16-le'))//2>4096 for t in messages):raise ValueError('Original message exceeds Telegram size limit')
    for index,text in enumerate(messages):
        response=journal.telegram('sendMessage',{'chat_id':destination,'text':text,'parse_mode':'Markdown'})
        r=response.get('result',{})
        if not response.get('ok') or str(r.get('chat',{}).get('id'))!=destination or not r.get('message_id'):raise ValueError('Unconfirmed delivery')
        journal.state[identity]['receipts'].append({'part':index+1,'message_id':r['message_id'],'date':r.get('date')});journal.persist()
    journal.state[identity].update(status='sent',source_dates=sorted(dates),parts=len(messages),market_count=len(opportunities),priced_holdings=len(holdings));journal.persist()
    print('Original report accepted. Parts',len(messages),'Yahoo dates',','.join(sorted(dates)),'priced holdings',len(holdings))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Stopped safely:',type(error).__name__,'. No automatic send retry.');sys.exit(1)
