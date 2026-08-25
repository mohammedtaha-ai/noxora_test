<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use App\Exceptions\ControlPlaneException;
use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Response;

class RequestContext
{
    public function handle(Request $request, Closure $next): Response
    {
        $requestId = $this->uuidHeaderOrGenerated($request, 'X-Request-Id');
        $correlationId = $this->uuidHeaderOrDefault($request, 'X-Correlation-Id', $requestId);
        $request->attributes->set('request_id', $requestId);
        $request->attributes->set('correlation_id', $correlationId);

        $response = $next($request);
        $response->headers->set('X-Request-Id', $requestId);
        $response->headers->set('X-Correlation-Id', $correlationId);

        return $response;
    }

    private function uuidHeaderOrGenerated(Request $request, string $header): string
    {
        if (! $request->headers->has($header)) {
            return (string) Str::uuid7();
        }

        return $this->requiredUuidHeader($request, $header);
    }

    private function uuidHeaderOrDefault(Request $request, string $header, string $default): string
    {
        if (! $request->headers->has($header)) {
            return $default;
        }

        return $this->requiredUuidHeader($request, $header);
    }

    private function requiredUuidHeader(Request $request, string $header): string
    {
        $value = (string) $request->header($header, '');
        if (! Str::isUuid($value)) {
            throw new ControlPlaneException('MALFORMED_REQUEST_IDENTIFIER', $header.' must be a UUID.', 400);
        }

        return $value;
    }
}
