// frontend/static/script.js

document.getElementById('addSaleForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const item = document.getElementById('item').value;
    const quantity = parseInt(document.getElementById('quantity').value);
    const price = parseFloat(document.getElementById('price').value);
    
    fetch('/add_sale', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ item, quantity, price }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Sale added successfully!');
            this.reset();
        }
    });
});

document.getElementById('getDailyTotalForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const date = document.getElementById('totalDate').value;
    
    fetch(`/get_daily_total?date=${date}`)
    .then(response => response.json())
    .then(data => {
        document.getElementById('dailyTotal').textContent = `Total sales for ${date}: KES ${data.total.toFixed(2)}`;
    });
});

document.getElementById('getDailySalesForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const date = document.getElementById('salesDate').value;
    
    fetch(`/get_daily_sales?date=${date}`)
    .then(response => response.json())
    .then(data => {
        const salesList = document.getElementById('dailySales');
        salesList.innerHTML = '';
        data.sales.forEach((sale, index) => {
            const li = document.createElement('li');
            li.className = 'bg-gray-100 p-3 rounded';
            li.textContent = `${index + 1}. Item: ${sale[0]}, Quantity: ${sale[1]}, Price: KES ${sale[2].toFixed(2)}`;
            salesList.appendChild(li);
        });
    });
});


document.getElementById('getMonthlyTotalForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const monthYear = document.getElementById('monthYear').value;
    const [year, month] = monthYear.split('-');
    
    fetch(`/get_monthly_total?year=${year}&month=${month}`)
    .then(response => response.json())
    .then(data => {
        document.getElementById('monthlyTotal').textContent = `Total sales for ${monthYear}: KES ${data.total.toFixed(2)}`;
    });
});


document.getElementById('getYearlyTotalForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const year = document.getElementById('year').value;
    
    fetch(`/get_yearly_total?year=${year}`)
    .then(response => response.json())
    .then(data => {
        document.getElementById('yearlyTotal').textContent = `Total sales for ${year}: KES ${data.total.toFixed(2)}`;
    });
});