<?php

declare(strict_types=1);

namespace App\Models;

class OutboxEvent extends ControlPlaneModel
{
    protected $table = 'outbox_events';

    protected $primaryKey = 'event_id';

    public $timestamps = false;

    protected function casts(): array
    {
        return [
            'payload' => 'array',
            'occurred_at' => 'datetime',
            'claimed_at' => 'datetime',
            'claim_expires_at' => 'datetime',
            'published_at' => 'datetime',
        ];
    }
}
