<?php

declare(strict_types=1);

namespace App\Models;

class Assignment extends ControlPlaneModel
{
    protected $table = 'assignments';

    protected function casts(): array
    {
        return [
            'available_from' => 'datetime',
            'available_until' => 'datetime',
        ];
    }

    public function scenarioVersion()
    {
        return $this->belongsTo(ScenarioVersion::class);
    }

    public function isAvailableAt(\DateTimeInterface $at): bool
    {
        return $this->status === 'active'
            && $this->available_from <= $at
            && ($this->available_until === null || $this->available_until > $at);
    }
}
