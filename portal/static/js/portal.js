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

  // サーバー再起動（ウインドウ閉じて新しく立ち上げ）
  const btnRestart = document.getElementById('btn-restart');
  if (btnRestart) {
    btnRestart.addEventListener('click', () => {
      navigator.sendBeacon('/api/restart');
      window.close();
    });
  }

  // サーバー終了（ウインドウも閉じる）
  const btnShutdown = document.getElementById('btn-shutdown');
  if (btnShutdown) {
    btnShutdown.addEventListener('click', () => {
      navigator.sendBeacon('/api/shutdown');
      window.close();
    });
  }
});
