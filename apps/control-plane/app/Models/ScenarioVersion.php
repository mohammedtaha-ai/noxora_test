<?php

declare(strict_types=1);

namespace App\Models;

class ScenarioVersion extends ControlPlaneModel
{
    protected $table = 'scenario_versions';

    protected function casts(): array
    {
        return [
            'metadata' => 'array',
            'published_at' => 'datetime',
        ];
    }

    public function scenario()
    {
        return $this->belongsTo(Scenario::class);
    }

    public function isPublished(): bool
    {
        return $this->status === 'published';
    }
}
