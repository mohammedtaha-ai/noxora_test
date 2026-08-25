<?php

declare(strict_types=1);

namespace App\Support;

use RuntimeException;

final class LocalDestructiveOperationGuard
{
    public static function assertAllowed(string $environment, string $host, string $database, mixed $explicitAllow): void
    {
        $isLocalEnvironment = in_array($environment, ['local', 'testing'], true);
        $isLoopback = in_array(strtolower($host), ['127.0.0.1', 'localhost', '::1'], true);
        $hasTestDatabaseName = str_contains(strtolower($database), '_test');
        $hasExplicitLocalOverride = in_array(strtolower((string) $explicitAllow), ['1', 'true', 'yes'], true);

        if (! $isLocalEnvironment || ! $isLoopback || (! $hasTestDatabaseName && ! $hasExplicitLocalOverride)) {
            throw new RuntimeException(
                'Destructive local tool refused: require APP_ENV local/testing, a loopback database host, and a database name containing _test or NEXORA_ALLOW_DESTRUCTIVE_LOCAL=1.'
            );
        }
    }
}
