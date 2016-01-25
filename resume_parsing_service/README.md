# Resume Service
Flask microservice for handling resume parsing.

## Oauth
This service requires Oauth2 and forwards the token from a requesting client to the auth server. That is, this service is not a registered client in the database.

## TODOS
Pylint reports that parselib in general has too many branches and statements. It would be good to break up some of the larger functions.
optic_parse_lib.parse_candidate_experiences has too many locals.
Improve general exceptions.
Consumer secret & token secret should ideally be environment variables.
Processing of images (from mobile!!!) could be speed improved if done on our own server? Investigate option such as pytesseract