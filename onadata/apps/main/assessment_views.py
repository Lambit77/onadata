import json
import os
import time
from datetime import datetime

import requests
from django.core.cache import cache
from django.http import JsonResponse
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView


#FETCH AND DISPLAY ONA FORM SUB AS JSON
def fetch_form_submissions(request, form_id):
    api_url = f"https://api.ona.io./api/v1/data/{form_id}"

    try:
        response = requests.get(api_url, timeout=10)

        if response.status_code == 404:
           return JsonResponse(
                {
                    "success": False,
                    "error": "Form not found",
                    "message": "No form submissions were found for the provided form ID.",
                },
                status=404,
            )

        if response.status_code in [401, 403]:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Access denied",
                    "message": "You do not have permission to view this form's submissions.",
                },
                status=response.status_code,
            )

        response.raise_for_status()

        data=response.json()
        return JsonResponse(data, safe=False)

    except requests.exceptions.Timeout:
        return JsonResponse(
            {
                "success": False,
                "error": "Request timeout",
                "message": "The request to the Ona API took too long. Please try again later.",
            },
            status=504,
        )

    except requests.exceptions.ConnectionError:
        return JsonResponse(
            {
                "success": False,
                "error": "Connection error",
                "message": "Unable to connect to the Ona API. Please check your network connection.",
            },
            status=503,
        )

    except requests.exceptions.RequestException:
        return JsonResponse(
            {
                "success": False,
                "error": "API request failed",
                "message": "An error occurred while fetching data from the Ona API.",
            },
            status=500,
        )

    except ValueError:
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid response",
                "message": "The Ona API returned a response that could not be read as JSON.",
            },
            status=500,
        )


class OAuthFormSubmissionsAPIView(APIView):
    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, form_id):
        start_time = datetime.now()
        start_perf = time.perf_counter()

        user = request.user
        user_role = "staff" if user.is_staff else "regular"
        refresh_cache = request.GET.get("refresh", "false").lower() == "true"

        cache_key = f"ona_form:{form_id}:user:{user.id}:role:{user_role}"

        if not refresh_cache:
            cached_data = cache.get(cache_key)

            if cached_data is not None:
                end_time = datetime.now()
                duration = time.perf_counter() - start_perf

                self.write_log(
                    request=request,
                    form_id=form_id,
                    response_data=cached_data,
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    cache_status="HIT",
                    status_code=200,
                )

                return JsonResponse(cached_data, safe=False, status=200)

        api_url = f"https://api.ona.io/api/v1/data/{form_id}"

        try:
            response = requests.get(api_url, timeout=10)

            if response.status_code == 404:
                response_data = {
                    "success": False,
                    "error": "Form not found",
                    "message": "No form submissions were found for the provided form ID.",
                }
                status_code = 404

            elif response.status_code in [401, 403]:
                response_data = {
                    "success": False,
                    "error": "Access denied",
                    "message": "You do not have permission to access this form data.",
                }
                status_code = response.status_code

            else:
                response.raise_for_status()
                response_data = response.json()
                status_code = 200

                cache.set(cache_key, response_data, timeout=300)

        except requests.exceptions.Timeout:
            response_data = {
                "success": False,
                "error": "Request timeout",
                "message": "The request to Ona API took too long.",
            }
            status_code = 504

        except requests.exceptions.ConnectionError:
            response_data = {
                "success": False,
                "error": "Connection error",
                "message": "Unable to connect to Ona API.",
            }
            status_code = 503

        except requests.exceptions.RequestException:
            response_data = {
                "success": False,
                "error": "API request failed",
                "message": "An error occurred while contacting Ona API.",
            }
            status_code = 500

        except ValueError:
            response_data = {
                "success": False,
                "error": "Invalid response",
                "message": "Ona API returned a response that could not be parsed as JSON.",
            }
            status_code = 500

        end_time = datetime.now()
        duration = time.perf_counter() - start_perf

        self.write_log(
            request=request,
            form_id=form_id,
            response_data=response_data,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            cache_status="BYPASS" if refresh_cache else "MISS",
            status_code=status_code,
        )

        return JsonResponse(response_data, safe=False, status=status_code)

    def write_log(
        self,
        request,
        form_id,
        response_data,
        start_time,
        end_time,
        duration,
        cache_status,
        status_code,
    ):
        log_dir = "api/logs"
        os.makedirs(log_dir, exist_ok=True)

        log_data = {
            "user_id": request.user.id,
            "username": request.user.username,
            "method": request.method,
            "path": request.path,
            "form_id": form_id,
            "query_params": dict(request.GET),
            "status_code": status_code,
            "cache_status": cache_status,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 4),
            "response_type": type(response_data).__name__,
        }

        log_file = os.path.join(log_dir, "api_requests.jsonl")

        with open(log_file, "a") as file:
            file.write(json.dumps(log_data) + "\n")