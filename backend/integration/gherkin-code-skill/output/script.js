const criteria = [
  'Users can choose a historical time period before starting.',
  'Users can interact with historical characters during the journey.',
  'User decisions change the story path and outcome.',
  'Users can review achievements and learning progress.'
];

const list = document.querySelector('#criteria-list');

criteria.forEach((item) => {
  const li = document.createElement('li');
  li.textContent = item;
  list.appendChild(li);
});
