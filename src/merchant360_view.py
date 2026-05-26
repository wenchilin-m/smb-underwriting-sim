"""
Editorial Merchant 360 view.

Renders the single-merchant underwriting case file as one self-contained HTML
document (editorial / newspaper aesthetic) driven by real model output. The
front-end is React compiled in-browser via Babel standalone; data is injected
as ``window.MERCHANTS``.

Design source: Claude Design handoff bundle "Merchant 360.html" (Source Serif 4
headlines, Helvetica body, JetBrains Mono numerics, green accent #15803d). The
design-tool tweaks panel has been removed; everything else is faithful.

Usage:
    from src.merchant360_view import render_merchant360_html
    html = render_merchant360_html(merchants)          # list[dict] from merchant360.build_merchants
    st.components.v1.html(html, height=2500, scrolling=True)
"""
from __future__ import annotations

import json

_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=1440" />
<title>Merchant 360 · Underwrite</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
<style>
  :root{
    --ink:#0b0b0b; --ink-2:#3d3d3d; --ink-3:#6b6b6b; --ink-4:#9a9a9a;
    --paper:#ffffff; --soft:#f4f4f1; --soft-2:#ececea; --rule:#e8e8e6; --rule-2:#d6d6d2;
    --green:__ACCENT__; --green-bright:__ACCENT__; --green-ink:#0a4a26;
    --red:#c8312a; --red-dark:#9b2620; --amber:#b6822b; --dark:#0d1f17; --dark-ink:#e9efe9;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0;background:var(--paper);color:var(--ink);font-family:"Helvetica Neue", Helvetica, Arial, sans-serif;font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
  body{min-width:1200px}
  .serif{font-family:"Source Serif 4", "Source Serif Pro", Georgia, serif;font-feature-settings:"ss01","ss02"}
  .mono{font-family:"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;font-variant-numeric:tabular-nums}
  .smallcaps{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);font-weight:500}
  a{color:inherit;text-decoration:none}
  button{font:inherit;cursor:pointer;border:0;background:none;color:inherit;padding:0}
  hr.rule{border:0;border-top:1px solid var(--rule);margin:0}
  .container{max-width:1440px;margin:0 auto;padding:0 56px}
  .topbar{display:flex;align-items:center;justify-content:space-between;padding:18px 56px;border-bottom:1px solid var(--rule);background:var(--paper);position:sticky;top:0;z-index:30}
  .brand{display:flex;align-items:center;gap:34px}
  .logo{font-family:"Source Serif 4",Georgia,serif;font-weight:700;letter-spacing:-.01em;font-size:22px}
  .logo .dot{display:inline-block;width:8px;height:8px;background:var(--green);border-radius:50%;vertical-align:1px;margin-right:8px}
  .nav{display:flex;gap:28px;font-size:13.5px}
  .nav a{color:var(--ink-2);position:relative;padding:6px 0}
  .nav a.on{color:var(--ink);font-weight:600}
  .nav a.on::after{content:"";position:absolute;left:0;right:0;bottom:-19px;height:2px;background:var(--ink)}
  .nav a:hover{color:var(--ink)}
  .top-right{display:flex;align-items:center;gap:22px}
  .pill-status{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;color:var(--green-ink);font-weight:600}
  .pill-status .blip{width:7px;height:7px;border-radius:50%;background:var(--green-bright);box-shadow:0 0 0 3px rgba(22,163,74,.18)}
  .btn-dark{background:var(--ink);color:#fff;padding:9px 16px;border-radius:6px;font-weight:600;font-size:13px;display:inline-flex;align-items:center;gap:8px}
  .btn-dark:hover{background:#222}
  .btn-light{background:#fff;border:1px solid var(--rule-2);padding:8px 14px;border-radius:6px;font-size:13px;font-weight:500;display:inline-flex;align-items:center;gap:8px}
  .btn-light:hover{border-color:#a8a8a4}
  .hero{padding:36px 0 18px;display:grid;grid-template-columns:1fr auto;gap:24px;align-items:flex-end;border-bottom:1px solid var(--ink);position:relative}
  .hero h1{font-family:"Source Serif 4",Georgia,serif;font-weight:500;font-size:84px;line-height:.95;letter-spacing:-.022em;margin:0}
  .hero .sub{margin-top:14px;max-width:560px;color:var(--ink-2);font-size:15.5px;line-height:1.45}
  .merchant-select{min-width:340px}
  .merchant-select .lbl{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);margin-bottom:6px}
  .merchant-select .picker{display:flex;align-items:center;justify-content:space-between;border:1px solid var(--ink);padding:11px 14px;border-radius:6px;background:#fff;font-weight:600;font-size:14.5px;gap:14px}
  .merchant-select .picker .meta{color:var(--ink-3);font-weight:400;font-size:12.5px;letter-spacing:.04em}
  .merchant-list{position:absolute;top:100%;left:0;right:0;background:#fff;border:1px solid var(--ink);border-top:0;z-index:10;max-height:320px;overflow:auto}
  .merchant-row{padding:12px 14px;display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;border-top:1px solid var(--rule);cursor:pointer}
  .merchant-row:first-child{border-top:0}
  .merchant-row:hover{background:var(--soft)}
  .merchant-row .id{font-family:"JetBrains Mono",monospace;font-size:12px;color:var(--ink-3)}
  .merchant-row .nm{font-weight:600}
  .merchant-row .verdict{font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:600}
  .bias{display:flex;align-items:flex-end;gap:22px;padding:14px 0 18px;border-bottom:1px solid var(--rule)}
  .bias-track{flex:1;display:flex;gap:3px;height:30px;align-items:flex-end}
  .bias-track .cell{flex:1;background:var(--soft-2);border-radius:1px}
  .bias-track .cell.dim{background:#d8d8d4}
  .bias-track .cell.now{background:var(--ink);height:100% !important}
  .bias-track .cell.win{background:var(--green-bright)}
  .bias-labels{display:flex;justify-content:space-between;font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);margin-top:6px}
  .bias-headline{font-family:"Source Serif 4",Georgia,serif;font-size:22px;font-weight:600;letter-spacing:-.01em;display:flex;align-items:baseline;gap:10px}
  .bias-headline .num{color:var(--green);font-weight:700}
  .bias-headline .tag{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);font-weight:500;font-family:"Helvetica Neue",sans-serif}
  .body{padding:32px 0 64px;display:grid;grid-template-columns:1fr 360px;gap:48px}
  .main-col{min-width:0}
  .side-col{min-width:0}
  .sec-head{display:flex;align-items:center;justify-content:space-between;padding:10px 0 12px}
  .ncard{border:1px solid var(--rule);background:#fff;display:flex;flex-direction:column;border-radius:6px;overflow:hidden;position:relative;transition:all .15s}
  .ncard .head{padding:14px 16px 0;display:flex;align-items:center;justify-content:space-between}
  .ncard .cat{font-size:11px;color:var(--ink-3);display:flex;align-items:center;gap:6px}
  .ncard .cat::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--ink);display:inline-block;margin-right:2px}
  .ncard .bookmark{color:var(--ink-3);opacity:.7}
  .decision{margin:8px 0 26px}
  .decision-head{display:flex;align-items:center;gap:14px;padding-bottom:14px;border-bottom:1px solid var(--rule)}
  .badge-approve{display:inline-flex;align-items:center;gap:8px;background:var(--green);color:#fff;border-radius:999px;padding:6px 14px 6px 10px;font-weight:700;font-size:13px;letter-spacing:.02em}
  .badge-approve .tick{width:14px;height:14px;border-radius:50%;background:#fff;color:var(--green);display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:900}
  .decision-headline{font-family:"Source Serif 4",Georgia,serif;font-size:22px;letter-spacing:-.008em;font-weight:500}
  .decision-headline em{font-style:italic;color:var(--green-ink)}
  .decision-meta{margin-left:auto;font-size:12.5px;color:var(--ink-3)}
  .decision-meta b{color:var(--ink)}
  .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-top:1px solid var(--rule)}
  .stat{padding:18px 22px;border-right:1px solid var(--rule);display:flex;flex-direction:column;gap:6px;position:relative;background:#fff}
  .stat:last-child{border-right:0}
  .stat .lbl{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);font-weight:500}
  .stat .val{font-family:"Source Serif 4",Georgia,serif;font-size:34px;font-weight:600;letter-spacing:-.012em;line-height:1.05;margin-top:2px}
  .stat .sub{font-size:12px;color:var(--ink-3);display:flex;align-items:center;gap:6px}
  .stat .delta{display:inline-flex;align-items:center;gap:3px;font-weight:600;font-size:11.5px}
  .stat .delta.up{color:var(--green)}
  .stat .delta.dn{color:var(--red)}
  .stat .spark{margin-top:6px}
  .stat .stripbar{position:absolute;left:0;right:0;bottom:0;height:4px}
  .stat .stripbar.green{background:var(--green-bright)}
  .stat .stripbar.red{background:var(--red)}
  .stat .stripbar.dark{background:var(--ink)}
  .stat .stripbar.amber{background:var(--amber)}
  .step{margin:34px 0 0}
  .step .step-tag{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--ink-3);font-weight:500;display:flex;align-items:center;gap:10px}
  .step .step-tag .n{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:1px solid var(--ink);font-size:10px;font-weight:700;letter-spacing:.05em;color:var(--ink);border-radius:50%;font-family:"JetBrains Mono",monospace}
  .step-card{border:1px solid var(--rule);border-radius:6px;background:#fff;margin-top:12px;overflow:hidden}
  .step-card .sc-head{display:flex;align-items:center;justify-content:space-between;padding:18px 22px;border-bottom:1px solid var(--rule)}
  .step-card .sc-head h3{font-family:"Source Serif 4",Georgia,serif;font-weight:600;font-size:22px;margin:0;letter-spacing:-.008em;display:flex;align-items:center;gap:10px}
  .step-card .sc-head h3 .ico{width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;color:var(--green)}
  .step-card .sc-head .actions{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-3)}
  .seg{display:inline-flex;border:1px solid var(--rule-2);border-radius:6px;overflow:hidden}
  .seg button{padding:5px 11px;font-size:12px;color:var(--ink-3);background:#fff}
  .seg button.on{background:var(--ink);color:#fff}
  .seg button + button{border-left:1px solid var(--rule-2)}
  .chart-wrap{padding:18px 22px 8px}
  .chart{width:100%;height:280px;display:block}
  .chart .grid line{stroke:var(--rule);stroke-dasharray:2 3}
  .chart .axis text{font-size:10.5px;fill:var(--ink-3);font-family:"JetBrains Mono",monospace}
  .chart .median{stroke:var(--ink);stroke-width:1.5;fill:none}
  .chart .median-future{stroke:var(--green);stroke-width:2;fill:none}
  .chart .dot{fill:var(--ink)}
  .chart .dot-fc{fill:var(--green)}
  .chart .baseline{stroke:var(--ink);stroke-width:1}
  .chart .marker{stroke:var(--ink);stroke-dasharray:2 3}
  .chart .anno{font-size:11px;fill:var(--ink-2)}
  .legend{display:flex;align-items:center;gap:18px;padding:0 22px 14px;font-size:11.5px;color:var(--ink-3)}
  .legend .swatch{width:16px;height:8px;display:inline-block;margin-right:6px;vertical-align:middle;border-radius:1px}
  .legend .swatch.band{background:rgba(21,128,61,.18)}
  .legend .swatch.actual{background:var(--ink)}
  .legend .swatch.fc{background:var(--green)}
  .collapse-row{display:flex;align-items:center;justify-content:space-between;padding:12px 22px;border-top:1px solid var(--rule);font-size:13px;color:var(--ink-2)}
  .collapse-row .lhs{display:flex;align-items:center;gap:10px}
  .signals{display:grid;grid-template-columns:repeat(3,1fr);gap:0}
  .signal{border-right:1px solid var(--rule);padding:18px 22px;position:relative;display:flex;flex-direction:column;gap:10px;min-height:200px}
  .signal:last-child{border-right:0}
  .signal .lbl{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);font-weight:500;display:flex;justify-content:space-between;align-items:center}
  .signal .val{font-family:"Source Serif 4",Georgia,serif;font-size:32px;font-weight:600;letter-spacing:-.012em;line-height:1}
  .signal .val .unit{font-size:18px;color:var(--ink-3);font-weight:500;margin-left:2px}
  .signal .note{font-size:12.5px;color:var(--ink-2);line-height:1.4}
  .signal .stripbar{position:absolute;left:0;right:0;bottom:0;height:4px}
  .signal .stripbar.green{background:var(--green-bright)}
  .signal .stripbar.red{background:var(--red)}
  .signal .stripbar.amber{background:var(--amber)}
  .offer{display:grid;grid-template-columns:1.4fr 1fr;gap:0}
  .offer-left{padding:24px;border-right:1px solid var(--rule)}
  .offer-right{padding:24px;background:var(--soft)}
  .offer-amount{font-family:"Source Serif 4",Georgia,serif;font-size:64px;font-weight:600;letter-spacing:-.022em;line-height:.95;color:var(--ink)}
  .offer-amount .sym{color:var(--ink-3);font-weight:500;font-size:38px;vertical-align:8px;margin-right:4px}
  .offer-terms{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}
  .term .lbl{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
  .term .val{font-family:"Source Serif 4",Georgia,serif;font-size:22px;font-weight:600;margin-top:2px}
  .term .val .unit{font-size:14px;color:var(--ink-3);font-weight:500;margin-left:3px}
  .offer-cta{display:flex;gap:10px;margin-top:20px}
  .btn-pri{background:var(--ink);color:#fff;border-radius:6px;padding:11px 18px;font-weight:600;font-size:13.5px;display:inline-flex;align-items:center;gap:8px}
  .btn-pri:hover{background:#222}
  .btn-sec{background:#fff;border:1px solid var(--rule-2);border-radius:6px;padding:10px 16px;font-weight:500;font-size:13.5px}
  .offer-right h4{font-family:"Source Serif 4",Georgia,serif;font-weight:600;font-size:16px;margin:0 0 10px}
  .reason-list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:10px}
  .reason-list li{display:grid;grid-template-columns:auto 1fr;gap:10px;font-size:13px;color:var(--ink-2)}
  .reason-list li .ind{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);margin-top:7px}
  .reason-list li.warn .ind{background:var(--amber)}
  .reason-list li b{color:var(--ink);font-weight:600}
  .monitor{padding:18px 22px 4px}
  .repay-row{display:grid;grid-template-columns:60px 1fr 80px;gap:10px;padding:8px 0;border-top:1px solid var(--rule);align-items:center;font-size:12.5px}
  .repay-row:first-child{border-top:0}
  .repay-row .lbl{color:var(--ink-3);font-family:"JetBrains Mono",monospace;font-size:11.5px}
  .repay-row .bar{height:18px;position:relative;background:var(--soft);border-radius:1px;overflow:hidden}
  .repay-row .bar .fill{position:absolute;left:0;top:0;bottom:0;background:var(--green);transition:width .4s}
  .repay-row .bar .proj{position:absolute;top:0;bottom:0;background:repeating-linear-gradient(45deg,var(--soft-2),var(--soft-2) 4px,#e0e0db 4px,#e0e0db 8px)}
  .repay-row .amt{text-align:right;font-family:"JetBrains Mono",monospace;font-size:12px}
  .side-card{border:1px solid var(--rule);border-radius:6px;background:#fff;margin-bottom:18px;overflow:hidden}
  .side-card .sh{padding:14px 16px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--rule)}
  .side-card .sh h4{font-family:"Source Serif 4",Georgia,serif;font-weight:600;margin:0;font-size:17px;letter-spacing:-.005em}
  .side-card .sb{padding:14px 16px}
  .idx-strip{display:flex;gap:3px;height:26px;align-items:flex-end;margin:2px 0 6px}
  .idx-strip .c{flex:1;background:var(--soft-2);border-radius:1px}
  .idx-strip .c.now{background:var(--ink);height:100% !important}
  .idx-labels{display:flex;justify-content:space-between;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
  .ai-card{border:1px solid var(--rule);border-radius:6px;margin-bottom:18px;overflow:hidden}
  .ai-trig{padding:12px 14px;display:flex;align-items:center;gap:10px;font-weight:600;border-bottom:1px solid var(--rule);font-size:14px}
  .ai-trig .plus{width:22px;height:22px;border-radius:50%;background:var(--ink);color:#fff;display:inline-flex;align-items:center;justify-content:center;font-weight:700}
  .ai-body{padding:14px 16px}
  .ai-body h5{font-family:"Source Serif 4",Georgia,serif;font-weight:600;font-size:18px;margin:0 0 10px}
  .ai-tabs{display:flex;gap:6px;margin:0 0 12px}
  .ai-tab{padding:5px 11px;border-radius:999px;font-size:12px;background:#fff;border:1px solid var(--rule-2);color:var(--ink-2);font-weight:500}
  .ai-tab.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  .ai-bullet{display:flex;gap:10px;font-size:13px;color:var(--ink-2);padding:6px 0;line-height:1.45}
  .ai-bullet::before{content:"";flex:0 0 5px;height:5px;border-radius:50%;background:var(--ink);margin-top:9px}
  .ai-bullet b{color:var(--ink);font-weight:600}
  .ai-more{display:flex;align-items:center;justify-content:space-between;font-size:11.5px;color:var(--ink-3);margin-top:8px;padding-top:10px;border-top:1px solid var(--rule)}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
  .chip{background:var(--soft);border:1px solid var(--rule);border-radius:999px;padding:5px 10px;font-size:11.5px;color:var(--ink-2)}
  .ask{display:flex;align-items:center;gap:8px;border:1px solid var(--rule-2);border-radius:999px;padding:8px 12px;margin-top:12px;background:#fff}
  .ask input{border:0;outline:0;font:inherit;flex:1;background:transparent;font-size:13px}
  .ask .send{width:28px;height:28px;border-radius:50%;background:var(--green);color:#fff;display:inline-flex;align-items:center;justify-content:center}
  .trend-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-top:1px solid var(--rule);font-size:13px}
  .trend-row:first-child{border-top:0}
  .trend-row .lhs{display:flex;align-items:center;gap:10px}
  .trend-row .dot{width:6px;height:6px;border-radius:50%;background:var(--ink)}
  .trend-row .dot.r{background:var(--red)}
  .trend-row .dot.g{background:var(--green-bright)}
  .trend-row .dot.a{background:var(--amber)}
  .trend-row .rhs{font-size:11.5px;color:var(--ink-3);font-family:"JetBrains Mono",monospace}
  .briefing{background:var(--dark);color:#fff;border-radius:6px;padding:24px 22px 22px;position:relative;overflow:hidden}
  .briefing h3{font-family:"Source Serif 4",Georgia,serif;font-weight:500;font-size:30px;line-height:1.05;letter-spacing:-.012em;margin:0 0 12px;color:#fff}
  .briefing p{color:#bcc8c0;font-size:13px;line-height:1.5;margin:0 0 18px}
  .briefing .nums{display:flex;align-items:baseline;gap:18px;margin:14px 0 18px}
  .briefing .nums .n{font-family:"Source Serif 4",Georgia,serif;font-weight:600;font-size:42px;line-height:1}
  .briefing .nums .u{color:#7a8a82;font-size:11px;letter-spacing:.18em;text-transform:uppercase;margin-left:6px;font-weight:500;align-self:center}
  .briefing .btn{background:#fff;color:var(--dark);border-radius:6px;padding:10px 14px;font-weight:600;font-size:13px;display:flex;align-items:center;justify-content:space-between}
  .briefing::after{content:"";position:absolute;right:-30px;top:-30px;width:140px;height:140px;border:1px solid rgba(255,255,255,.08);border-radius:50%}
  .briefing::before{content:"";position:absolute;right:-80px;bottom:-80px;width:220px;height:220px;border:1px solid rgba(255,255,255,.05);border-radius:50%}
  .footer{border-top:1px solid var(--ink);margin-top:48px;padding:24px 56px;display:flex;justify-content:space-between;font-size:12px;color:var(--ink-3)}
  .footer .colofon{font-family:"Source Serif 4",Georgia,serif;font-style:italic}
  .row{display:flex;align-items:center;gap:8px}
</style>
</head>
<body>

<header class="topbar">
  <div class="brand">
    <div class="logo"><span class="dot"></span>UNDERWRITE</div>
    <nav class="nav">
      <a href="#">Portfolio</a>
      <a href="#" class="on">Merchant 360</a>
      <a href="#">Pipeline</a>
      <a href="#">Policies</a>
      <a href="#">Timelines</a>
    </nav>
  </div>
  <div class="top-right">
    <span class="pill-status"><span class="blip"></span><span id="healthy-count">Healthy</span></span>
    <a href="#" style="font-size:13px;color:var(--ink-2)">Casebook</a>
    <button class="btn-dark">Approve &amp; Disburse <span style="opacity:.6">&rarr;</span></button>
  </div>
</header>

<div id="root"></div>

<footer class="footer">
  <div class="colofon">Underwrite &middot; Single-merchant case view &middot; quantile-regression model</div>
  <div>v4.2 &middot; Live model &middot; Policy 2026-02</div>
</footer>

<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" crossorigin="anonymous"></script>

<script>
  window.MERCHANTS = __MERCHANTS_JSON__;
  window.ACCENT = "__ACCENT__";
  (function(){
    var healthy = window.MERCHANTS.filter(function(m){return m.verdict === "approve";}).length;
    var el = document.getElementById("healthy-count");
    if (el) el.textContent = healthy + " of " + window.MERCHANTS.length + " approve";
  })();
</script>

<script type="text/babel">
// ── Icons + chart components ─────────────────────────────────────────────────
const Icon = {
  Chev: ({size=12, dir="right"})=>{
    const r = {right:0, down:90, up:-90, left:180}[dir]||0;
    return (<svg width={size} height={size} viewBox="0 0 12 12" style={{transform:`rotate(${r}deg)`}}>
      <path d="M4 2 L8 6 L4 10" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="square"/></svg>);
  },
  Tick: ({size=12})=>(<svg width={size} height={size} viewBox="0 0 12 12"><path d="M2 6.5 L5 9 L10 3" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>),
  Bookmark: ({size=14})=>(<svg width={size} height={size} viewBox="0 0 14 14" fill="none"><path d="M3 2 H11 V12 L7 9 L3 12 Z" stroke="currentColor" strokeWidth="1.2"/></svg>),
  Clock: ({size=14})=>(<svg width={size} height={size} viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.1"/><path d="M7 4 V7 L9 8.5" stroke="currentColor" strokeWidth="1.1" fill="none" strokeLinecap="round"/></svg>),
  Spark: ({size=14})=>(<svg width={size} height={size} viewBox="0 0 14 14" fill="none"><path d="M2 9 L5 6 L7 8 L12 3" stroke="currentColor" strokeWidth="1.4" fill="none"/></svg>),
  Plus: ({size=14})=>(<svg width={size} height={size} viewBox="0 0 14 14"><path d="M7 3 V11 M3 7 H11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>),
  Send: ({size=14})=>(<svg width={size} height={size} viewBox="0 0 14 14" fill="none"><path d="M2 7 L12 2 L10 12 L7 8 Z" stroke="currentColor" strokeWidth="1.2" fill="currentColor" fillOpacity=".0"/></svg>),
  Caret: ({size=10})=>(<svg width={size} height={size} viewBox="0 0 10 10"><path d="M2 3.5 L5 6.5 L8 3.5" stroke="currentColor" strokeWidth="1.4" fill="none"/></svg>),
  Store: ({size=20})=>(<svg width={size} height={size} viewBox="0 0 20 20" fill="none"><path d="M3 7 L4.5 3.5 H15.5 L17 7 M3 7 V16 H17 V7 M3 7 H17 M7 16 V11 H13 V16" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/></svg>),
  Dots: ({size=16})=>(<svg width={size} height={size} viewBox="0 0 16 16"><circle cx="3.5" cy="8" r="1.4" fill="currentColor"/><circle cx="8" cy="8" r="1.4" fill="currentColor"/><circle cx="12.5" cy="8" r="1.4" fill="currentColor"/></svg>),
};

function Sparkline({values, w=80, h=24, stroke="currentColor", fill="none"}){
  if(!values || values.length<2) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const span = (max-min)||1, step = w/(values.length-1);
  const pts = values.map((v,i)=>[i*step, h - ((v-min)/span)*(h-2) - 1]);
  const d = "M "+pts.map(p=>p.join(",")).join(" L ");
  return (<svg width={w} height={h} style={{display:"block"}}><path d={d} stroke={stroke} strokeWidth="1.4" fill={fill}/></svg>);
}

function ForecastChart({merchant}){
  const W = 800, H = 280, PAD = {l:48, r:24, t:18, b:34};
  const innerW = W - PAD.l - PAD.r, innerH = H - PAD.t - PAD.b;
  const actual = merchant.actual, fc = merchant.forecast;
  const bandHi = merchant.bandHi, bandLo = merchant.bandLo;
  const allPoints = [...actual, ...fc], months = merchant.months, totalPts = allPoints.length;
  const allVals = [...allPoints, ...bandHi, ...bandLo];
  const yMin = Math.min(...allVals)*0.92, yMax = Math.max(...allVals)*1.05;
  const xStep = innerW/(totalPts-1);
  const x = i => PAD.l + i*xStep;
  const y = v => PAD.t + (1 - (v-yMin)/(yMax-yMin))*innerH;
  const yTicks = 4, ticks = [];
  for(let i=0;i<=yTicks;i++){ const v = yMin + (yMax-yMin)*(i/yTicks); ticks.push({v, y: PAD.t + (1-i/yTicks)*innerH}); }
  const actualPath = "M " + actual.map((v,i)=>`${x(i)},${y(v)}`).join(" L ");
  const lastActualIdx = actual.length-1;
  const fcStartPt = `${x(lastActualIdx)},${y(actual[lastActualIdx])}`;
  const fcPath = "M " + fcStartPt + " L " + fc.map((v,i)=>`${x(lastActualIdx+1+i)},${y(v)}`).join(" L ");
  const bandTopPts = bandHi.map((v,i)=>`${x(lastActualIdx+1+i)},${y(v)}`);
  const bandBotPts = bandLo.map((v,i)=>`${x(lastActualIdx+1+i)},${y(v)}`).reverse();
  const anchor = `${x(lastActualIdx)},${y(actual[lastActualIdx])}`;
  const bandPath = "M " + anchor + " L " + bandTopPts.join(" L ") + " L " + bandBotPts.join(" L ") + " L " + anchor + " Z";
  const nowX = x(lastActualIdx) + xStep*0.5;
  const fmt = v => "$"+Math.round(v/1000)+"k";
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
      <defs><linearGradient id="bandgrad" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stopColor="var(--green)" stopOpacity=".18"/>
        <stop offset="100%" stopColor="var(--green)" stopOpacity=".04"/></linearGradient></defs>
      <g className="grid">{ticks.map((t,i)=>(<line key={i} x1={PAD.l} x2={W-PAD.r} y1={t.y} y2={t.y}/>))}</g>
      <g className="axis">{ticks.map((t,i)=>(<text key={i} x={PAD.l-8} y={t.y+3} textAnchor="end">{fmt(t.v)}</text>))}</g>
      <g className="axis">{months.map((m,i)=>(<text key={i} x={x(i)} y={H-PAD.b+18} textAnchor="middle" fill={i>lastActualIdx?"var(--green)":"var(--ink-3)"}>{m}</text>))}</g>
      <path d={bandPath} fill="url(#bandgrad)" />
      <line className="marker" x1={nowX} x2={nowX} y1={PAD.t} y2={H-PAD.b}/>
      <text className="anno" x={nowX+6} y={PAD.t+10}>&uarr; today</text>
      <path className="median" d={actualPath} />
      <path className="median-future" d={fcPath} strokeDasharray="3 3"/>
      {actual.map((v,i)=>(<circle key={"a"+i} className="dot" cx={x(i)} cy={y(v)} r="3"/>))}
      {fc.map((v,i)=>(<circle key={"f"+i} className="dot-fc" cx={x(lastActualIdx+1+i)} cy={y(v)} r="3.5"/>))}
      <line className="baseline" x1={PAD.l} x2={W-PAD.r} y1={H-PAD.b} y2={H-PAD.b}/>
      <line className="baseline" x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={H-PAD.b}/>
      <g>
        <circle cx={x(totalPts-1)} cy={y(bandHi[bandHi.length-1])} r="2.5" fill="var(--green)" opacity=".6"/>
        <text className="anno" x={x(totalPts-1)-4} y={y(bandHi[bandHi.length-1])-6} textAnchor="end" fill="var(--green-ink)">P90 {fmt(bandHi[bandHi.length-1])}</text>
        <circle cx={x(totalPts-1)} cy={y(bandLo[bandLo.length-1])} r="2.5" fill="var(--green)" opacity=".6"/>
        <text className="anno" x={x(totalPts-1)-4} y={y(bandLo[bandLo.length-1])+14} textAnchor="end" fill="var(--green-ink)">P10 {fmt(bandLo[bandLo.length-1])}</text>
      </g>
    </svg>
  );
}

function RepayTimeline({merchant}){
  const total = merchant.advance + merchant.fee, per = total / merchant.term;
  const monthNames = ["Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb"];
  const rows = [];
  for(let i=0;i<merchant.term;i++){ rows.push({month: monthNames[i], actual: i<2, amt: per}); }
  return (
    <div className="monitor">
      {rows.map((r,i)=>(
        <div className="repay-row" key={i}>
          <div className="lbl">{r.month}</div>
          <div className="bar">
            {r.actual ? <div className="fill" style={{width:"100%"}}></div>
                      : <div className="proj" style={{left:0, width: (i===2?70:i===3?50:i===4?30:15)+"%"}}></div>}
          </div>
          <div className="amt">{r.actual ? "$"+Math.round(r.amt).toLocaleString() : <span style={{color:"var(--ink-3)"}}>${Math.round(r.amt).toLocaleString()}</span>}</div>
        </div>
      ))}
    </div>
  );
}

window.Icon = Icon;
window.Sparkline = Sparkline;
window.ForecastChart = ForecastChart;
window.RepayTimeline = RepayTimeline;
</script>

<script type="text/babel">
// ── Main app composition ─────────────────────────────────────────────────────
const { useState } = React;

function App(){
  const [merchantIdx, setMerchantIdx] = useState(0);
  const [pickerOpen, setPickerOpen] = useState(false);
  const merchant = window.MERCHANTS[merchantIdx];
  const [openForecast, setOpenForecast] = useState(false);
  const [aiTab, setAiTab] = useState("Today");
  const [askVal, setAskVal] = useState("");

  const cohortN = {sushi:"412", coffee:"1,284", sandwich:"906"}[merchant.kind] || "1,000";
  const volTone = merchant.volatility<20?"green":merchant.volatility<30?"amber":"red";

  return (
    <div className="container">
      <section className="hero">
        <div>
          <div className="smallcaps" style={{marginBottom:14, display:"flex", alignItems:"center", gap:10}}>
            <Icon.Store size={16}/> Merchant 360 &middot; Single-merchant underwriting view
          </div>
          <h1 className="serif">{merchant.name}</h1>
          <div className="sub">Underwriting case file built from {merchant.tenure} of transaction history. P10 / P50 / P90 revenue paths plus the recommended advance the model would extend today.</div>
        </div>
        <div className="merchant-select" style={{position:"relative"}}>
          <div className="lbl">Case</div>
          <div className="picker" onClick={()=>setPickerOpen(p=>!p)} style={{cursor:"pointer"}}>
            <span>
              <span className="mono" style={{color:"var(--ink-3)", marginRight:8}}>{merchant.id}</span>
              {merchant.name}
              <span className="meta" style={{marginLeft:8}}>&middot; {merchant.kind} &middot; {merchant.tenure}</span>
            </span>
            <Icon.Caret/>
          </div>
          {pickerOpen && (
            <div className="merchant-list">
              {window.MERCHANTS.map((m,i)=>(
                <div className="merchant-row" key={m.id+"-"+m.store} onClick={()=>{setMerchantIdx(i);setPickerOpen(false);setOpenForecast(false);}}>
                  <span className="id">{m.id}</span>
                  <span><span className="nm">{m.name}</span> <span style={{color:"var(--ink-3)",fontSize:12,marginLeft:6}}>&middot; {m.kind} &middot; {m.tenure}</span></span>
                  <span className="verdict" style={{color: m.verdict==="approve"?"var(--green)":m.verdict==="review"?"var(--amber)":"var(--red)"}}>{m.verdict}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="bias">
        <div style={{flex:1}}>
          <div className="bias-headline">
            <span className="num">{merchant.riskIndex}</span>
            <span>Risk Index &middot; {merchant.riskLabel}</span>
            <span className="tag">trailing 30 days</span>
          </div>
          <div className="bias-track" style={{marginTop:12}}>
            {Array.from({length: 28}).map((_,i)=>{
              const nowPos = Math.round(merchant.riskIndex/100*27);
              const isNow = i===nowPos;
              const heights = [22,18,14,10,16,14,18,22,20,12,16,18,14,10,18,14,22,18,12,16,14,18,30,20,16,14,12,18];
              const cls = i<8 ? "dim" : i>nowPos-3 && i<nowPos ? "win" : "";
              return <div key={i} className={"cell "+(isNow?"now":cls)} style={{height: heights[i]+"px"}}/>;
            })}
          </div>
          <div className="bias-labels">
            <span>Distress</span><span>Stress</span><span>Stable</span>
            <span style={{color:"var(--green-ink)", fontWeight:600}}>Healthy</span>
          </div>
        </div>
      </section>

      <div className="body">
        <div className="main-col">
          <DecisionCard merchant={merchant}/>

          <div className="step">
            <div className="step-tag"><span className="n">1</span>Step One &middot; Pre-decision</div>
            <div className="step-card">
              <div className="sc-head">
                <h3><span className="ico"><Icon.Spark size={18}/></span>Revenue forecast</h3>
                <div className="actions"><div className="seg"><button className="on">P10/50/90</button><button>Daily</button><button>Cohort</button></div></div>
              </div>
              <div className="chart-wrap"><ForecastChart merchant={merchant}/></div>
              <div className="legend">
                <span><span className="swatch band"></span>P10 &ndash; P90 band</span>
                <span><span className="swatch actual"></span>Trailing actual</span>
                <span><span className="swatch fc"></span>P50 forecast</span>
                <span style={{marginLeft:"auto",color:"var(--ink-3)"}}>{merchant.qrAvailable?"Quantile regression":"Rolling fallback ±20%"} &middot; tier {merchant.riskTier}</span>
              </div>
              <div className={openForecast?"open":""}>
                <div className="collapse-row" onClick={()=>setOpenForecast(o=>!o)} style={{cursor:"pointer"}}>
                  <div className="lhs"><span className="chev" style={{display:"inline-block",transform: openForecast?"rotate(90deg)":"rotate(0deg)", transition:"transform .2s"}}><Icon.Chev/></span><b style={{color:"var(--ink)"}}>Forecast details</b><span className="smallcaps" style={{background:"var(--soft)",padding:"2px 8px",borderRadius:4}}>{openForecast?"expanded":"collapsed"}</span></div>
                  <div style={{color:"var(--ink-3)",fontSize:12}}>next-month P50 {"$"+Math.round(merchant.forecast[0]).toLocaleString()}</div>
                </div>
                {openForecast && (
                  <div style={{padding:"4px 22px 22px", display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:18, borderTop:"1px solid var(--rule)", paddingTop:18}}>
                    {[
                      {l:"P10 floor", v:"$"+Math.round(merchant.bandLo[0]).toLocaleString(), n:"downside scenario"},
                      {l:"P50 median", v:"$"+Math.round(merchant.forecast[0]).toLocaleString(), n:"expected next month"},
                      {l:"P90 ceiling", v:"$"+Math.round(merchant.bandHi[0]).toLocaleString(), n:"upside scenario"},
                      {l:"Model", v:merchant.qrAvailable?"QR":"Fallback", n:"tier "+merchant.riskTier},
                    ].map((d,i)=>(
                      <div key={i}><div className="smallcaps">{d.l}</div><div className="serif" style={{fontSize:22,fontWeight:600,marginTop:2}}>{d.v}</div><div style={{fontSize:11.5,color:"var(--ink-3)"}}>{d.n}</div></div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="step">
            <div className="step-tag"><span className="n">2</span>Step Two &middot; Risk signals</div>
            <div className="step-card">
              <div className="sc-head"><h3>Cohort-relative behaviour</h3><div className="actions"><span>Compared against {merchant.kind} cohort &middot; n={cohortN}</span></div></div>
              <div className="signals">
                <Signal lbl="Revenue volatility" val={merchant.volatility} unit="%" tone={volTone}
                  note={`Coefficient of variation drives risk tiering. ${merchant.volatility<20?"Well within policy.":merchant.volatility<30?"Within tolerance, watch closely.":"Above the 25% policy threshold."}`}
                  spark={[merchant.volatility+3, merchant.volatility+1, merchant.volatility+2, merchant.volatility, merchant.volatility-1, merchant.volatility]} />
                <Signal lbl="History on file" val={merchant.months.length>0?merchant.tenure.split(" ")[0]:"0"} unit={merchant.tenure.split(" ")[1]||""} tone={merchant.qrAvailable?"green":"amber"}
                  note={merchant.qrAvailable?"Enough history to fit the quantile regression model directly.":"Below the 12-month threshold for QR; rolling fallback used."}
                  spark={merchant.actual} />
                <Signal lbl="Risk tier" val={merchant.riskTier} unit="" tone={merchant.riskTier==="A"?"green":merchant.riskTier==="B"?"amber":"red"}
                  note={`Tier ${merchant.riskTier} sets advance rate and factor rate. ${merchant.riskTier==="A"?"Best terms.":merchant.riskTier==="B"?"Standard terms.":"Conservative terms."}`}
                  spark={[merchant.bandLo[0], merchant.forecast[0], merchant.bandHi[0]]} />
              </div>
            </div>
          </div>

          <div className="step">
            <div className="step-tag"><span className="n">3</span>Step Three &middot; Offer construction</div>
            <div className="step-card">
              <div className="sc-head"><h3>Recommended advance</h3><div className="actions"><button className="btn-light"><Icon.Dots/></button><button className="btn-light">Adjust manually</button></div></div>
              <div className="offer">
                <div className="offer-left">
                  <div className="smallcaps">Advance amount</div>
                  <div className="offer-amount"><span className="sym">$</span>{merchant.advance.toLocaleString()}</div>
                  <div className="offer-terms">
                    <div className="term"><div className="lbl">Fixed fee</div><div className="val">${merchant.fee.toLocaleString()}</div></div>
                    <div className="term"><div className="lbl">Term</div><div className="val">{merchant.term}<span className="unit">months</span></div></div>
                    <div className="term"><div className="lbl">Repay rate</div><div className="val">{Math.round(merchant.repayRate*100)}<span className="unit">% of daily revenue</span></div></div>
                    <div className="term"><div className="lbl">APR (effective)</div><div className="val">{merchant.effApr}<span className="unit">%</span></div></div>
                  </div>
                  <div className="offer-cta"><button className="btn-pri">Send offer <Icon.Chev/></button><button className="btn-sec">Save for committee</button></div>
                </div>
                <div className="offer-right">
                  <h4>Why this number</h4>
                  <ul className="reason-list">
                    {merchant.reasons.map((r,i)=>(<li key={i} className={r.ok?"":"warn"}><span className="ind"></span><span><b>{r.head}</b> {r.tail}</span></li>))}
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <div className="step">
            <div className="step-tag"><span className="n">4</span>Step Four &middot; Post-decision monitor</div>
            <div className="step-card">
              <div className="sc-head"><h3>Repayment trajectory</h3><div className="actions"><span>{merchant.term}-month plan &middot; if funded</span></div></div>
              <RepayTimeline merchant={merchant}/>
              <div className="legend" style={{paddingTop:14}}>
                <span><span className="swatch fc"></span>Realised</span>
                <span><span className="swatch" style={{background:"repeating-linear-gradient(45deg,#e0e0db,#e0e0db 3px,#f4f4f1 3px,#f4f4f1 6px)"}}></span>Projected (illustrative)</span>
                <span style={{marginLeft:"auto",color:"var(--ink-3)"}}>Post-issuance view &middot; activates after disbursement</span>
              </div>
            </div>
          </div>
        </div>

        <aside className="side-col">
          <div className="side-card">
            <div className="sh"><h4>Risk Index</h4><span style={{color:"var(--ink-3)"}}><Icon.Clock/></span></div>
            <div className="sb">
              <div className="idx-strip">
                {Array.from({length:22}).map((_,i)=>{
                  const heights = [10,12,8,14,10,16,12,10,14,12,8,16,12,18,14,12,18,14,16,18,24,20];
                  const isNow = i===Math.round(merchant.riskIndex/100*21);
                  return <div key={i} className={"c "+(isNow?"now":"")} style={{height: heights[i]+"px"}}/>;
                })}
              </div>
              <div className="idx-labels"><span>Risky</span><span>Stress</span><span>Stable</span><span style={{color:"var(--green-ink)",fontWeight:600}}>{merchant.riskIndex} {merchant.riskLabel}</span></div>
            </div>
          </div>

          <div className="ai-card">
            <div className="ai-trig"><span className="plus"><Icon.Plus/></span>AI Underwriter</div>
            <div className="ai-body">
              <h5>Case summary</h5>
              <div className="ai-tabs">{["Today","This week","Trailing 90d"].map(x=>(<button key={x} className={"ai-tab "+(aiTab===x?"on":"")} onClick={()=>setAiTab(x)}>{x}</button>))}</div>
              <div>{merchant.ai.map((line,i)=>(<div className="ai-bullet" key={i}><span>{line}</span></div>))}</div>
              <div className="ai-more"><span>Derived from model output</span><a href="#" style={{color:"var(--ink)",fontWeight:600,display:"flex",alignItems:"center",gap:6}}>Show full <Icon.Chev/></a></div>
              <div className="chips"><span className="chip">Volatility deep-dive</span><span className="chip">Compare cohort</span><span className="chip">Counterfactual offer</span></div>
              <div className="ask"><input value={askVal} onChange={e=>setAskVal(e.target.value)} placeholder="Ask about this merchant..."/><button className="send"><Icon.Send/></button></div>
            </div>
          </div>

          <div className="side-card">
            <div className="sh"><h4>Recent flags</h4></div>
            <div className="sb" style={{padding:"4px 16px 12px"}}>
              {merchant.flags.map((f,i)=>(<div key={i} className="trend-row"><div className="lhs"><span className={"dot "+(f.sev==="g"?"g":f.sev==="r"?"r":"a")}></span><span>{f.text}</span></div><div className="rhs">{i===0?"2h":i===1?"yest":"3d"}</div></div>))}
              <div className="trend-row"><div className="lhs"><span className="dot g"></span><span>Bank balance refreshed</span></div><div className="rhs">7d</div></div>
            </div>
          </div>

          <div className="briefing">
            <div className="smallcaps" style={{color:"#7a8a82", marginBottom:14, letterSpacing:".18em"}}>Portfolio Briefing</div>
            <h3>Renewals open in 14 days</h3>
            <p>Several merchants in your book qualify for early-renewal offers under the May 2026 policy. Send batched offers from the pipeline view.</p>
            <div className="nums"><div><span className="n">{window.MERCHANTS.length}</span><span className="u">in book</span></div><div><span className="n">14</span><span className="u">days</span></div></div>
            <button className="btn">Open pipeline <span>&rsaquo;</span></button>
          </div>
        </aside>
      </div>
    </div>
  );
}

function DecisionCard({merchant}){
  const v = {
    approve: {bg:"var(--green)", txt:"Approve", em:"risk stable"},
    review:  {bg:"var(--amber)", txt:"Review",  em:"manual sign-off"},
    decline: {bg:"var(--red)",   txt:"Decline", em:"policy breach"},
  }[merchant.verdict];
  const volStrip = merchant.volatility<20?"green":merchant.volatility<30?"amber":"red";
  return (
    <div className="ncard" style={{marginTop:0}}>
      <div className="head" style={{paddingTop:18, paddingBottom:14}}>
        <span className="cat">Hero summary <span style={{marginLeft:8,fontSize:11,color:"var(--ink-3)"}}>&middot; always visible</span></span>
        <span className="bookmark"><Icon.Bookmark/></span>
      </div>
      <div style={{padding:"0 18px 18px"}}>
        <div className="decision-head">
          <span className="badge-approve" style={{background:v.bg}}><span className="tick" style={{color:v.bg}}><Icon.Tick/></span> {v.txt}</span>
          <div className="decision-headline">Recommended offer ready &middot; <em>{v.em}</em></div>
          <div className="decision-meta">Decision <b>{merchant.id}-2026-05</b> &middot; model v4.2</div>
        </div>
      </div>
      <div className="stats">
        <Stat lbl="Avg monthly revenue" val={"$"+merchant.avgRev.toLocaleString()} delta={merchant.revDelta} up={merchant.revUp} sub="vs first month on file" strip="green" spark={merchant.actual.slice(-6)}/>
        <Stat lbl="Revenue volatility" val={merchant.volatility+"%"} sub="coefficient of variation" strip={volStrip} spark={merchant.actual.slice(-6)}/>
        <Stat lbl="Recommended advance" val={"$"+merchant.advance.toLocaleString()} delta={merchant.advPctP50+"% of P50"} up sub={"tier "+merchant.riskTier} strip="dark"/>
        <Stat lbl="Fixed fee &middot; term" val={"$"+merchant.fee.toLocaleString()} sub={`${merchant.term}-month plan &middot; ${Math.round(merchant.repayRate*100)}% repay`} strip="dark"/>
      </div>
    </div>
  );
}

function Stat({lbl, val, sub, delta, up, strip, spark}){
  return (
    <div className="stat">
      <div className="lbl">{lbl}</div>
      <div className="val">{val}</div>
      <div className="sub">{delta && <span className={"delta "+(up?"up":"dn")}>{up?"▲":"▼"} {delta}</span>}<span dangerouslySetInnerHTML={{__html: sub}}/></div>
      {spark && <div className="spark"><Sparkline values={spark} w={120} h={20} stroke={strip==="green"?"var(--green)":strip==="red"?"var(--red)":"var(--ink)"}/></div>}
      <div className={"stripbar "+strip}></div>
    </div>
  );
}

function Signal({lbl, val, unit, tone, note, spark}){
  return (
    <div className="signal">
      <div className="lbl"><span>{lbl}</span><span style={{color:"var(--ink-3)",fontSize:10.5}}>vs cohort</span></div>
      <div className="val">{val}<span className="unit">{unit}</span></div>
      <div className="note">{note}</div>
      {spark && <div style={{marginTop:"auto"}}><Sparkline values={spark} w={220} h={32} stroke={tone==="green"?"var(--green)":tone==="red"?"var(--red)":"var(--amber)"}/></div>}
      <div className={"stripbar "+tone}></div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
</script>

</body>
</html>
"""


def render_merchant360_html(merchants: list[dict], accent: str = "#15803d") -> str:
    """Return the full editorial Merchant 360 HTML document with data injected."""
    data_json = json.dumps(merchants)
    return (
        _HTML_TEMPLATE
        .replace("__MERCHANTS_JSON__", data_json)
        .replace("__ACCENT__", accent)
    )
