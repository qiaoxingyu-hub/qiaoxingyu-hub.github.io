import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import (
    get_latest, get_events, get_predictions, get_stats,
    save_prediction, resolve_prediction, save_event, today,
    get_rules, save_rule, trigger_rule, save_trade, close_trade, get_trades, get_portfolio_summary
)
from collector import all as collect_all
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
import uvicorn
from pathlib import Path

BASE = Path(__file__).parent
STATIC = BASE / "static"; STATIC.mkdir(exist_ok=True)

JINJA = Environment(loader=FileSystemLoader(str(BASE / "templates")), autoescape=True, auto_reload=True)
def render(name, **ctx): return HTMLResponse(JINJA.get_template(name).render(**ctx))

app = FastAPI(title="InfoRecon")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

@app.get("/")
async def dashboard(request: Request):
    return render("index.html", request=request,
        indicators=get_latest(), events=get_events(pending=True)[:15],
        stats=get_stats(), pending_predictions=get_predictions(status="pending")[:10])

@app.get("/collect")
async def collect():
    r = collect_all()
    return HTMLResponse("<pre>"+json.dumps(r,ensure_ascii=False,indent=2)+'</pre><p><a href="/">返回</a></p>')

@app.get("/predictions")
async def predictions_page(request: Request):
    return render("predictions.html", request=request,
        predictions=get_predictions(), stats=get_stats())

@app.post("/predictions/add")
async def add_pred(category:str=Form(...),subject:str=Form(...),direction:str=Form(...),
                   target_value:str=Form(""),timeframe:str=Form("3m"),confidence:int=Form(5),reasoning:str=Form("")):
    save_prediction(category,subject,direction,target_value,timeframe,confidence,reasoning)
    return RedirectResponse(url="/predictions",status_code=303)

@app.post("/predictions/resolve/{pid}")
async def resolve_pred(pid:int,status:str=Form(...),actual_outcome:str=Form("")):
    resolve_prediction(pid,status,actual_outcome); return RedirectResponse(url="/predictions",status_code=303)

@app.get("/events")
async def events_page(request:Request,category:str=""):
    ev = get_events(cat=category) if category else get_events()
    return render("events.html",request=request,events=ev,current_category=category)

@app.get("/events/add")
async def add_event_page(request:Request):
    return render("event_add.html",request=request)

@app.post("/events/add")
async def add_event(date:str=Form(...),title:str=Form(...),description:str=Form(""),
                    category:str=Form("other"),impact:int=Form(5),ticker:str=Form(""),
                    sentiment:str=Form("neutral"),impact_metric:float=Form(0.0)):
    save_event(date,title,description,category,impact,ticker,sentiment,impact_metric)
    return RedirectResponse(url="/events",status_code=303)

@app.get("/rules")
async def rules_page(request:Request):
    return render("rules.html",request=request,rules=get_rules(),portfolio=get_portfolio_summary())

@app.post("/rules/add")
async def add_rule(name:str=Form(...),description:str=Form(""),condition_type:str=Form(...),
                   condition_params:str=Form(""),action_type:str=Form(...),action_target:str=Form("")):
    try: params = json.loads(condition_params)
    except: params = {}
    save_rule(name,description,condition_type,params,action_type,action_target)
    return RedirectResponse(url="/rules",status_code=303)

@app.post("/rules/trigger/{rid}")
async def trigger_rule_endpoint(rid:int,success:int=Form(1)):
    trigger_rule(rid,bool(success)); return RedirectResponse(url="/rules",status_code=303)

@app.get("/trades")
async def trades_page(request:Request):
    return render("trades.html",request=request,trades=get_trades(),portfolio=get_portfolio_summary())

@app.post("/trades/add")
async def add_trade(ticker:str=Form(...),trade_type:str=Form(...),price:float=Form(...),
                    quantity:float=Form(1),notes:str=Form(""),rule_id:int=Form(0),prediction_id:int=Form(0)):
    save_trade(ticker,trade_type,price,quantity,price*quantity,
               rule_id if rule_id>0 else None,prediction_id if prediction_id>0 else None,notes)
    return RedirectResponse(url="/trades",status_code=303)

@app.post("/trades/close/{tid}")
async def close_trade_endpoint(tid:int,close_price:float=Form(...)):
    close_trade(tid,close_price); return RedirectResponse(url="/trades",status_code=303)

@app.get("/api/indicators")
async def api_indicators(): return get_latest()

@app.get("/api/stats")
async def api_stats(): return get_stats()

@app.on_event("startup")
async def startup():
    try: collect_all()
    except: pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8899))
    print("="*50)
    print(f"  InfoRecon v2 - http://0.0.0.0:{port}")
    print("="*50)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
