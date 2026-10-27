# Nautilus vNext — Tool Rack / TradingView Proportion Pass

This folder contains a **visual/read-only patch layer** for the latest verified
HF15-era Nautilus source. It is intentionally separate from the Tool Rack
strategy core.

## User goals locked into vNext

- Keep the default/persistent ~3-contract / 45-minute chart behavior.
- Make the chart **narrower and visually taller**, closer to TradingView rather
  than stretched side-to-side.
- Give the **engine feed more width** and slightly larger text.
- Make the **current position panel a compact horizontal rectangle**, not a
  large square consuming the right rail.
- Restore **MAX @ $1** potential: maximum percent gain and maximum gross PAPER
  profit if the binary contract reaches $1.
- Add a thin **Tool Rack shadow strip** showing:
  - owned territory;
  - primary tool;
  - compatible overlay;
  - resolved intent;
  - exact Commander/block reason.
- Keep all Nautilus output read-only. Tool Rack display state has zero order,
  veto, resize, custody, or execution authority.

## Visual comparison basis

The TradingView reference uses BTCUSD 1-minute candles and the user's normal
approximately **3 contracts / 45 minutes** view. The main visual difference is
proportion: TradingView gives the price candles a taller working field, while
Nautilus currently gives too much horizontal width to the chart and too much
vertical space to the right-side position card.

vNext changes the Bridge proportions from roughly:

```
feed 24% | chart 52% | right 24%
```

to:

```
feed 31% | chart 47% | right 22%
```

and increases the candle-price pane from **75% to 83%** of chart height.

The user's saved chart span remains authoritative; vNext does not force-reset a
custom zoom.

## Known HF15 visual-base hashes

The patch refuses unknown source drift by default.

- `nautilus/static/bridge.css`
  `319df6d1ef02f7e96854d59a2a16ac8dccb70f7f90dbb1209f8b936108bf23b8`
- `nautilus/static/chart.js`
  `a62f9a0f6dd2ed1a363ba73c7aa78074bdb39a5aa9d2690a5ac9dcd895c40a82`
- `nautilus/static/app.js`
  `2b1ad96cc52832b4789bf09fddb7f1d58e238e25d2d40af44c71d70a8247ca64`
- `nautilus/adapter.py`
  `8b7735773bfb58868c0c44cd3a959cf62ade1223e072e01045250b29bcb4a096`
- `nautilus/static/index.html`
  `0a9bc18d5bc776b43489c10cff7119fc93d36b0e192b38f52c3627dd055f887f`

## Strategy boundary

Nautilus consumes Tool Rack **shadow output only**. It never imports a Tool
Rack trading class and never executes a Tool Rack intent.

The shadow file is expected at:

```
<TACHYOS_TOOL_RACK_SHADOW_ROOT>/<PAPER_RUN_NAME>/TOOL_RACK_SHADOW_STATUS.json
```

Default Windows shadow root:

```
E:\\TachyosToolRackShadow
```
