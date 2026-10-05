document.getElementById('ask-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const box = document.getElementById('answer-box');
  const answer = document.getElementById('answer-text');
  const button = event.currentTarget.querySelector('button');
  button.disabled = true;
  box.style.display = 'block';
  answer.textContent = 'Preparing your answer…';
  try {
    const response = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content },
      body: new URLSearchParams({ question: document.getElementById('question').value }),
    });
    const data = await response.json();
    answer.textContent = data.answer || data.error || 'An answer could not be generated.';
  } catch { answer.textContent = 'The request could not be completed. Please try again.'; }
  finally { button.disabled = false; }
});
