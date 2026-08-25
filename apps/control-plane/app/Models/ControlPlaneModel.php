<?php

declare(strict_types=1);

namespace App\Models;

use App\Models\Concerns\UsesUuid7;
use Illuminate\Database\Eloquent\Model;

abstract class ControlPlaneModel extends Model
{
    use UsesUuid7;

    protected $guarded = [];
}
