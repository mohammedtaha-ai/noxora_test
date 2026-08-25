<?php

declare(strict_types=1);

namespace App\Models;

class AuditLog extends ControlPlaneModel
{
    protected $table = 'audit_logs';

    public $timestamps = false;

    protected function casts(): array
    {
        return [
            'metadata' => 'array',
            'occurred_at' => 'datetime',
        ];
    }
}
