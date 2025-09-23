(function(global){
  'use strict';

  function getCookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : null;
  }
  function setCookie(name, value, days = 365) {
    const maxAge = days * 24 * 60 * 60;
    document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAge}; samesite=lax`;
  }
  function getCSRFToken() { return getCookie('csrftoken'); }

  function resolveUserId() {

    if (global.CURRENT_USER_ID && String(global.CURRENT_USER_ID).trim()) {
      return String(global.CURRENT_USER_ID).trim();
    }

    const c = getCookie('user_id');
    if (c) return c;

    try {
      const raw = localStorage.getItem('user_info');
      if (raw) {
        const u = JSON.parse(raw);
        if (u?.user_id) return u.user_id;
        if (u?.id) return u.id;
        if (u?.uid) return u.uid;
        if (u?.email) return `user_${u.email}`;
      }
    } catch (_) {}

    const guest = 'guest_' + Math.random().toString(36).slice(2, 10);
    try { localStorage.setItem('user_info', JSON.stringify({ user_id: guest })); } catch (_) {}
    setCookie('user_id', guest, 365);
    return guest;
  }

  function getSpeechRecognitionCtor() {
    return global.SpeechRecognition || global.webkitSpeechRecognition || null;
  }

  function isLikelyHtml(str = "") {
    return /<\/?[a-z][\s\S]*>/i.test(String(str).trim());
  }

  global.getCookie = getCookie;       
  global.setCookie = setCookie;       
  global.getCSRFToken = getCSRFToken; 
  global.resolveUserId = resolveUserId; 
  global.getSpeechRecognitionCtor = getSpeechRecognitionCtor;
  global.isLikelyHtml = isLikelyHtml;
})(window);
