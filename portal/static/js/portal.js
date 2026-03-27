// データツールのタブ切り替え
function switchTool(tool) {
  const frame = document.getElementById('data-frame');
  if (!frame) return;

  const urls = { kintai: '/legacy/data/kintai', overtime: '/legacy/data/overtime' };
  frame.src = urls[tool] || urls.kintai;

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.includes(
      tool === 'kintai' ? '勤怠' : '残業'
    ));
  });
}

// サイドバーのアクティブ状態（現在URLに基づく）
document.addEventListener('DOMContentLoaded', () => {
  const path = location.pathname.replace(/\/$/, '') || '/';
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href').replace(/\/$/, '') || '/';
    if (path === href) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
});
