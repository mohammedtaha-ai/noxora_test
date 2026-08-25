<?php

declare(strict_types=1);

namespace App\Models;

class Scenario extends ControlPlaneModel
{
    protected $table = 'scenarios';

    public function versions()
    {
        return $this->hasMany(ScenarioVersion::class);
    }
}
