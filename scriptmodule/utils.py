from rest_framework.response import Response
import jwt
from jwt.exceptions import ExpiredSignatureError
from rest_framework import status


def token_validator(request):
    if not request.META.get('HTTP_AUTHORIZATION'):
        return {}

    jwt_token = request.META.get('HTTP_AUTHORIZATION').split(' ')[1]
    try:
        decoded = jwt.decode(jwt_token, key='2SASHBuG5I4TV0oH2J7MzTpfACgIbe5uWYZYQu6O0EMhbVS8VrlsJgJu6gsAJRz3',
                             algorithms='HS256')
        return {'user_id': decoded.get('user_id'), status: 200}
    except ExpiredSignatureError as error:
        print(error)
        return {}
