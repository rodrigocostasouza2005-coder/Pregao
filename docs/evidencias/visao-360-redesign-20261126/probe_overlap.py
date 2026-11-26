import json

from playwright.sync_api import sync_playwright

JS = """() => {
  const info = (sel) => [...document.querySelectorAll(sel)].map(el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {sel, top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height),
            over: cs.overflow, pos: cs.position, txt: (el.textContent||'').slice(0,40)};
  });
  const status = document.querySelector('.v360-status');
  const parent = status ? status.closest('[data-testid="stMarkdownContainer"]') : null;
  const wrapper = parent ? parent.parentElement : null;
  const acoes = document.querySelector('.st-key-v360_acoes');
  const r = (el) => el ? (({top,bottom,height}) => ({top:Math.round(top),bottom:Math.round(bottom),h:Math.round(height)}))(el.getBoundingClientRect()) : null;
  return {
    status: r(status),
    markdownContainer: r(parent),
    wrapper: r(wrapper),
    wrapperStyle: wrapper ? {h: getComputedStyle(wrapper).height, over: getComputedStyle(wrapper).overflow, cls: wrapper.className} : null,
    acoes: r(acoes),
    cotacao: r(document.querySelector('.v360-cotacao')),
    cab: r(document.querySelector('.v360-cab')),
    metricas: info('.v360-cotacao .ds-metricas'),
    wrapperCS: wrapper ? (({display,height,maxHeight,overflow,position,flex,alignSelf}) =>
        ({display,height,maxHeight,overflow,position,flex,alignSelf}))(getComputedStyle(wrapper)) : null,
    containerCS: parent ? (({display,height,overflow,position}) =>
        ({display,height,overflow,position}))(getComputedStyle(parent)) : null,
    paiDoWrapperCS: wrapper && wrapper.parentElement ? (({display,height,overflow,flexDirection,gap}) =>
        ({display,height,overflow,flexDirection,gap}))(getComputedStyle(wrapper.parentElement)) : null,
    statusCS: status ? (({display,height,marginTop,lineHeight,position,float:f}) =>
        ({display,height,marginTop,lineHeight,position,float:f}))(getComputedStyle(status)) : null,
    cadeia: (() => {
      const saida = []; let el = status;
      while (el && saida.length < 10) {
        const cs = getComputedStyle(el);
        saida.push({tag: el.tagName.toLowerCase(), cls: (el.className||'').toString().slice(0,42),
                    testid: el.getAttribute('data-testid'),
                    h: Math.round(el.getBoundingClientRect().height),
                    scrollH: el.scrollHeight,
                    display: cs.display, flexShrink: cs.flexShrink, minHeight: cs.minHeight,
                    flexBasis: cs.flexBasis, alignItems: cs.alignItems, gap: cs.rowGap});
        el = el.parentElement;
      }
      return saida;
    })(),
    experimento: (() => {
      const cab = document.querySelector('.v360-cabecalho');
      if (!cab) return null;
      const cont = cab.closest('[data-testid="stMarkdownContainer"]');
      const md = cont.closest('.stMarkdown');
      const cs = getComputedStyle(cont);
      const antes = Math.round(md.getBoundingClientRect().height);
      cab.style.marginBottom = '1rem';
      const comMargem = Math.round(md.getBoundingClientRect().height);
      cab.style.marginBottom = '';
      return {
        marginBottomDoContainer: cs.marginBottom,
        marginBottomDoMd: getComputedStyle(md).marginBottom,
        alturaMdAntes: antes, alturaMdComMargem1rem: comMargem,
      };
    })(),
    filhosDoContainer: parent ? [...parent.children].map(el => ({
        cls: (el.className||'').toString().slice(0,40),
        h: Math.round(el.getBoundingClientRect().height),
        top: Math.round(el.getBoundingClientRect().top)})) : null,
  };
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1200})
    pg.goto("http://localhost:8599", wait_until="networkidle")
    pg.wait_for_selector(".v360-ticker", timeout=60_000)
    pg.wait_for_timeout(1500)
    print(json.dumps(pg.evaluate(JS), indent=2, ensure_ascii=False))
    b.close()
