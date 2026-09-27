/**
 * Hermes Desktop plugin: Model Router
 *
 * A visual model selector for a tiered model stack. Adds three things to the
 * Hermes Desktop app:
 *
 *   1. a right-hand pane listing every tier with its live model;
 *   2. a status-bar chip showing the model currently in use;
 *   3. ⌘K palette entries ("Router: Deep → deepseek-v4-pro").
 *
 * Clicking a tier writes `/model <alias>` into the composer WITHOUT sending
 * it — you confirm with Enter. Nothing is switched behind your back.
 *
 * Install: put this file at
 *   ~/.hermes/desktop-plugins/model-router/plugin.js
 * The folder name must match the `id` exported below, and the app has to be
 * restarted (⌘Q, then reopen) before the plugin is loaded.
 *
 * Adapted from a personal DeepSeek + OpenRouter + Ollama stack; edit TIERS to
 * match your own. Paired with mcp_auto_router.py, which does the same routing
 * automatically from a task description.
 */

import { PALETTE_AREA, STATUSBAR_AREAS, haptic, host, useValue } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'model-router'

// ---------------------------------------------------------------------------
// Your stack. `model` is whatever the composer accepts after /model — a model
// id, or an alias declared under `aliases:` in ~/.hermes/config.yaml.
// ---------------------------------------------------------------------------
const TIERS = [
  {
    id: 'easy',
    icon: '⚡',
    label: 'Fast',
    model: 'deepseek-flash',
    note: 'Volume: translations, files, link checks'
  },
  {
    id: 'medium',
    icon: '🎯',
    label: 'Mid',
    model: 'or-qwen',
    note: 'Drafting and synthesis (~$0.03 / 1000 calls)'
  },
  {
    id: 'hard',
    icon: '🔥',
    label: 'Deep',
    model: 'deepseek-v4-pro',
    note: 'Papers, grant proposals, deep analysis'
  },
  {
    id: 'offline',
    icon: '💻',
    label: 'Local',
    model: 'gemma3:12b',
    note: 'Offline, sensitive data, $0'
  }
]

/** Write the command into the composer; the user confirms with Enter. */
function pick(model) {
  haptic('tap')
  void host.composer.insertText(null, `/model ${model}`)
}

function TierRow({ tier }) {
  return jsx('button', {
    type: 'button',
    className:
      'flex w-full items-start gap-2 rounded border border-(--ui-border) px-2 py-1.5 text-left ' +
      'transition-colors hover:bg-(--chrome-action-hover)',
    onClick: () => pick(tier.model),
    children: jsxs('span', {
      className: 'flex flex-col gap-0.5',
      children: [
        jsxs('span', {
          className: 'flex items-center gap-1.5 text-xs font-medium',
          children: [
            jsx('span', { children: tier.icon }),
            jsx('span', { children: `${tier.label} — ${tier.model}` })
          ]
        }),
        jsx('span', {
          className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
          children: tier.note
        })
      ]
    })
  })
}

function RouterPane() {
  const model = useValue(host.state.model)

  return jsxs('div', {
    className: 'flex h-full flex-col gap-2 p-3 text-sm',
    children: [
      jsx('div', { className: 'font-medium', children: 'Model router' }),
      jsxs('div', {
        className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
        children: ['active now: ', jsx('strong', { children: model || '—' })]
      }),
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: TIERS.map(tier => jsx(TierRow, { tier }, tier.id))
      }),
      jsx('div', {
        className: 'mt-auto text-[0.6875rem] text-(--ui-text-tertiary)',
        children: 'Click writes the command into the composer. Enter applies it.'
      })
    ]
  })
}

function RouterChip() {
  const model = useValue(host.state.model)

  return jsx('button', {
    type: 'button',
    className:
      'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] transition-colors ' +
      'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground',
    onClick: () => {
      haptic('tap')
      host.notify({ kind: 'info', message: `Active model: ${model || '—'}` })
    },
    children: `◆ ${model || 'router'}`
  })
}

export default {
  id: ID,
  name: 'Model Router',
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'router',
      data: { placement: 'right', width: '264px' },
      render: () => jsx(RouterPane, {})
    })

    ctx.register({
      id: 'chip',
      area: STATUSBAR_AREAS.right,
      order: 140,
      render: () => jsx(RouterChip, {})
    })

    ctx.registerMany(
      TIERS.map(tier => ({
        id: `route-${tier.id}`,
        area: PALETTE_AREA,
        data: {
          id: `${ID}.${tier.id}`,
          label: `Router: ${tier.label} → ${tier.model}`,
          keywords: ['router', 'model', tier.id, tier.model],
          run: () => pick(tier.model)
        }
      }))
    )
  }
}
