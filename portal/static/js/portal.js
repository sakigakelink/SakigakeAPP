document.addEventListener('DOMContentLoaded', () => {
  const path = location.pathname.replace(/\/$/, '') || '/';

  // サイドバーのアクティブ状態
  document.querySelectorAll('.nav-link[href]').forEach(link => {
    const href = link.getAttribute('href').replace(/\/$/, '') || '/';
    link.classList.toggle('active', path === href);
  });

  // サブメニュー: 子がアクティブなら親グループを開く
  document.querySelectorAll('.nav-group').forEach(group => {
    if (group.querySelector('.nav-sub-link.active')) {
      group.classList.add('open');
    }
  });

  // サブメニュートグル
  document.querySelectorAll('.nav-group-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('.nav-group').classList.toggle('open');
    });
  });

  // 再読込: iframe内のページをリロード
  const btnReload = document.getElementById('btn-reload');
  if (btnReload) {
    btnReload.addEventListener('click', () => {
      const iframe = document.querySelector('.app-frame');
      if (iframe) {
        iframe.contentWindow.location.reload();
      } else {
        location.reload();
      }
    });
  }

  // 再起動: サーバー再起動→同じウィンドウで自動リロード
  const btnRestart = document.getElementById('btn-restart');
  if (btnRestart) {
    btnRestart.addEventListener('click', () => {
      fetch('/api/restart', {method:'POST'});
      document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-size:1.2rem;color:#666">再起動中...</div>';
      const poll = setInterval(() => {
        fetch('/').then(r => { if (r.ok) { clearInterval(poll); location.reload(); } }).catch(() => {});
      }, 1000);
    });
  }

  // 終了: サーバー停止+ウィンドウ閉じる
  const btnShutdown = document.getElementById('btn-shutdown');
  if (btnShutdown) {
    btnShutdown.addEventListener('click', () => {
      fetch('/api/shutdown', {method:'POST'});
      setTimeout(() => window.close(), 500);
    });
  }
});
