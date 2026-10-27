/* 鴨 Dakku demo: on a phone, a small note on how to get the best of it. Inside another app's browser
 * (Instagram, Discord…), open it in Safari or Chrome; in the browser, add it to the Home Screen. Not on
 * computers, not once it's opened from the Home Screen, and not again once closed. */
(() => {
  const KEY = 'dakku-demo:tip-closed';
  const ua = navigator.userAgent;
  const ios = /iPhone|iPod/.test(ua) || (/iPad|Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  const android = /Android/.test(ua);
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if (!(ios || android) || standalone) return;
  try { if (localStorage.getItem(KEY)) return; } catch { /* private mode: show it */ }
  // another app's browser: those can't add to the Home Screen
  const inApp = /Instagram|FBAN|FBAV|FB_IAB|Line\/|Snapchat|TikTok|musical_ly|Discord|Twitter|LinkedInApp|GSA\//.test(ua)
    || (ios && !/Safari\//.test(ua));
  const browser = ios ? 'Safari' : 'Chrome';
  const text = inApp
    ? `For the full app, open this page in <b>${browser}</b>: tap <b>${ios ? '⋯ or the compass' : '⋮'}</b>, then <b>Open in ${ios ? 'Safari' : 'browser'}</b>.`
    : ios
      ? 'For the best experience, add Dakku to your Home Screen: tap <b>Share</b>, then <b>Add to Home Screen</b>.'
      : 'For the best experience, add Dakku to your Home Screen: tap <b>⋮</b>, then <b>Add to Home screen</b>.';
  const show = () => {
    const el = document.createElement('div');
    el.setAttribute('role', 'note');
    el.innerHTML = `<span style="font-size:20px;line-height:1" aria-hidden="true">鴨</span><span style="flex:1">${text}</span>`
      + '<button type="button" aria-label="Close" style="all:unset;cursor:pointer;padding:2px 6px;font-size:20px;line-height:1;color:var(--ink-2)">×</button>';
    Object.assign(el.style, {
      position: 'fixed', left: '12px', right: '12px', zIndex: 50,
      bottom: 'calc(var(--tabbar-h, 58px) + env(safe-area-inset-bottom, 0px) + 12px)',
      display: 'flex', gap: '10px', alignItems: 'center', padding: '12px 12px 12px 14px',
      background: 'var(--surface-2)', color: 'var(--ink)', border: '1px solid var(--line)', borderRadius: '16px',
      font: '14px/1.4 var(--body, system-ui, sans-serif)', boxShadow: '0 10px 30px rgb(0 0 0 / .35)',
    });
    el.querySelector('button').addEventListener('click', () => {
      el.remove();
      try { localStorage.setItem(KEY, '1'); } catch { /* fine */ }
    });
    document.body.appendChild(el);
  };
  addEventListener('load', () => setTimeout(show, 1500));
})();
