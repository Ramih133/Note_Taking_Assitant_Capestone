import os
import json
import base64
import chainlit as cl
from itsdangerous import TimestampSigner, BadSignature
from database import connect
from analysis.rag import collect, retrieve, generate
from chainlit.input_widget import Select

# Read the FastAPI session
@cl.header_auth_callback
def login(headers):
    from http.cookies import SimpleCookie
    cookies = SimpleCookie(headers.get('cookie', ''))
    if 'session' not in cookies:
        return None
    try:
        signed = cookies['session'].value
        data = TimestampSigner(os.getenv('SECRET_KEY', 'local-development-only-change-me')).unsign(signed, max_age=28800)
        uid = int(json.loads(base64.b64decode(data))['uid'])
        with connect() as db:
            user = db.execute('SELECT id FROM users WHERE id=?', (uid,)).fetchone()
        if user:
            return cl.User(identifier=str(uid))
    except (BadSignature, ValueError, KeyError, TypeError):
        return None

# Show classes that belong to the user
@cl.on_chat_start
async def start():
    uid = int(cl.user_session.get('user').identifier)
    with connect() as db:
        courses = db.execute('SELECT id, name FROM courses WHERE user_id=?', (uid,)).fetchall()
    choices = {str(c['id']) + ' — ' + c['name']: c['id'] for c in courses}
    cl.user_session.set('courses', choices)
    if not choices:
        await cl.Message(content='Create a class and save notes in Note Assistant first.').send()
        return
    settings = await cl.ChatSettings([Select(id='course', label='Course', values=list(choices), initial_index=0)]).send()
    cl.user_session.set('course', settings.get('course'))
    await cl.Message(content='Ask me a question about your course notes.').send()

@cl.on_settings_update
async def settings_update(settings):
    cl.user_session.set('course', settings.get('course'))

@cl.on_message
async def message(msg):
    uid = int(cl.user_session.get('user').identifier)
    cid = (cl.user_session.get('courses') or {}).get(cl.user_session.get('course'))
    if not cid:
        await cl.Message(content='Choose a course first.').send()
        return
    try:
        # Find relevant notes before asking the ai
        sources = await cl.make_async(collect)(uid, cid)
        selected = retrieve(sources, msg.content[:2000])
        if not selected:
            await cl.Message(content='No relevant notes found. Try different keywords.').send()
            return
        answer, model = await cl.make_async(generate)(selected, msg.content[:2000])
        answer += '\n\n**Sources**\n' + '\n'.join(f"{i}. {s['title']}" for i,s in enumerate(selected,1))
        await cl.Message(content=answer).send()
    except Exception:
        await cl.Message(content='Could not generate an answer. Check your model setup.').send()
