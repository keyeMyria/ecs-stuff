from candidate_service.candidate_app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8005, use_reloader=True, debug=False)
