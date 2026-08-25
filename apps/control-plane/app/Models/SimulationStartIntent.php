<?php

declare(strict_types=1);

namespace App\Models;

class SimulationStartIntent extends ControlPlaneModel
{
    protected $table = 'simulation_start_intents';

    protected function casts(): array
    {
        return ['requested_at' => 'datetime'];
    }

    public function assignment()
    {
        return $this->belongsTo(Assignment::class);
    }
}
