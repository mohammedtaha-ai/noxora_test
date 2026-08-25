<?php

declare(strict_types=1);

namespace Tests\Unit\ControlPlane;

use App\Support\LocalDestructiveOperationGuard;
use RuntimeException;
use Tests\TestCase;

class LocalDestructiveOperationGuardTest extends TestCase
{
    public function test_local_test_database_on_loopback_is_allowed(): void
    {
        LocalDestructiveOperationGuard::assertAllowed('testing', '127.0.0.1', 'nexora_control_plane_test', null);
        $this->addToAssertionCount(1);
    }

    public function test_production_remote_and_unmarked_database_contexts_are_refused(): void
    {
        foreach ([
            ['production', '127.0.0.1', 'nexora_control_plane_test', null],
            ['local', 'db.internal.example', 'nexora_control_plane_test', null],
            ['local', 'localhost', 'nexora_control_plane', null],
        ] as [$environment, $host, $database, $override]) {
            try {
                LocalDestructiveOperationGuard::assertAllowed($environment, $host, $database, $override);
                $this->fail('Expected destructive tool guard to refuse unsafe context.');
            } catch (RuntimeException $exception) {
                $this->assertStringContainsString('Destructive local tool refused', $exception->getMessage());
            }
        }
    }

    public function test_explicit_override_does_not_bypass_environment_or_loopback_requirements(): void
    {
        LocalDestructiveOperationGuard::assertAllowed('local', '::1', 'nexora_control_plane', '1');
        $this->addToAssertionCount(1);

        $this->expectException(RuntimeException::class);
        LocalDestructiveOperationGuard::assertAllowed('production', 'localhost', 'nexora_control_plane', '1');
    }
}
