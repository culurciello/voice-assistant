import ollama

response = ollama.chat(
    model='llama3.2-vision',
    messages=[{
        'role': 'user',
        'content': 'What color sweater am I wearing?',
        'images': ['camview.jpg'],
        'stream': True,
        # 'context': 'no context',
        # 'prompt': 'What color sweater am I wearing?',
    }]
)

# print(response)
print(response['message']['content'])


response = ollama.chat(
    model='llama3.2-vision',
    messages=[{
        'role': 'user',
        'content': 'What is in the background?',
        'images': ['camview.jpg'],
        'stream': True,
        # 'context': 'no context',
        # 'prompt': 'What color sweater am I wearing?',
    }]
)

print(response['message']['content'])



