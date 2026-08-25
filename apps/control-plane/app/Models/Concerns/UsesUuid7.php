<?php

declare(strict_types=1);

namespace App\Models\Concerns;

use Illuminate\Support\Str;

trait UsesUuid7
{
    public function initializeUsesUuid7(): void
    {
        $this->incrementing = false;
        $this->keyType = 'string';
    }

    protected static function bootUsesUuid7(): void
    {
        static::creating(function (self $model): void {
            if (! $model->getKey()) {
                $model->{$model->getKeyName()} = (string) Str::uuid7();
            }
        });
    }
}
