/* Applies the saved light/dark choice before the page paints (avoids a flash of the wrong theme).
   No saved choice = follow the operating system. */
(function () {
  try {
    var t = localStorage.getItem('hrmis.theme');
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
  } catch (e) { /* storage blocked: follow the system */ }
})();
