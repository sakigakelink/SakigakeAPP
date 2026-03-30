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

  // ページ再読込
  const btnReload = document.getElementById('btn-reload');
  if (btnReload) {
    btnReload.addEventListener('click', () => {
      location.reload();
    });
  }
});
