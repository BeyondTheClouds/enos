#!/bin/bash

scenarios=$1
times=$2
concurrency=$3
waiting=$4

for scenario in $(cat $scenarios | grep -v '^#'); do
    sed -i "s/times: .*/times: $times/g" $scenario
    sed -i "s/concurrency: .*/concurrency: $concurrency/g" $scenario
    # json case
    sed -i "s/\"times\": .*/\"times\": $times,/g" $scenario
    sed -i "s/\"concurrency\": .*/\"concurrency\": $concurrency,/g" $scenario
    rally task validate $scenario
    echo  $scenario
    rally task start $scenario #--deployment $3
    sleep $waiting
done
