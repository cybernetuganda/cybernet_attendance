from werkzeug.security import generate_password_hash

def sign_in(app_module, client):
    with app_module.db() as connection:
        connection.execute('INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)',
                           ('admin',generate_password_hash('test-password-123'),app_module.now().isoformat()))
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf']
    response = client.post('/login',data={'csrf':token,'username':'admin','password':'test-password-123'})
    assert response.status_code == 302 and response.location == '/', response.status_code
    with client.session_transaction() as session:
        return session['csrf']
