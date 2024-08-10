document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('addSaleForm').addEventListener('submit', handleAddSale);
    document.getElementById('mpesaPaymentForm').addEventListener('submit', handleMpesaPayment);
    document.getElementById('getDailyTotalForm').addEventListener('submit', handleGetDailyTotal);
    document.getElementById('getDailySalesForm').addEventListener('submit', handleGetDailySales);
    document.getElementById('getMonthlyTotalForm').addEventListener('submit', handleGetMonthlyTotal);
    document.getElementById('getYearlyTotalForm').addEventListener('submit', handleGetYearlyTotal);
});

function handleAddSale(e) {
    e.preventDefault();
    const item = document.getElementById('item').value;
    const quantity = parseInt(document.getElementById('quantity').value);
    const price = parseFloat(document.getElementById('price').value);

    fetch('/add_sale', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item, quantity, price }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Sale added successfully!');
            e.target.reset();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while adding the sale.');
    });
}

function handleMpesaPayment(e) {
    e.preventDefault();
    const phone_number = document.getElementById('phone_number').value;
    const amount = parseFloat(document.getElementById('payment_amount').value);

    fetch('/initiate_payment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number, amount }),
    })
    .then(response => response.json())
    .then(data => {
        const statusElement = document.getElementById('mpesaPaymentStatus');
        if (data.success) {
            statusElement.textContent = 'Payment initiated successfully. Please complete the payment on your phone.';
        } else {
            statusElement.textContent = `Payment failed: ${data.error || data.errorMessage}`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('mpesaPaymentStatus').textContent = 'An error occurred while initiating the payment.';
    });
}

function handleGetDailyTotal(e) {
    e.preventDefault();
    const date = document.getElementById('totalDate').value;

    fetch(`/get_daily_total?date=${date}`)
    .then(response => response.json())
    .then(data => {
        document.getElementById('dailyTotal').textContent = `Total sales for ${date}: KES ${data.total.toFixed(2)}`;
    });
}

function handleGetDailySales(e) {
    e.preventDefault();
    const date = document.getElementById('salesDate').value;

    fetch(`/get_daily_sales?date=${date}`)
    .then(response => response.json())
    .then(data => {
        const salesList = document.getElementById('dailySales');
        salesList.innerHTML = '';
        data.sales.forEach((sale, index) => {
            const li = document.createElement('li');
            li.className = 'bg-gray-100 p-3 rounded mb-2 flex justify-between items-center';
            li.innerHTML = `
                <span>${index + 1}. Item: ${sale.item}, Quantity: ${sale.quantity}, Price: KES ${sale.price.toFixed(2)}</span>
                <button class="delete-btn bg-red-500 text-white px-2 py-1 rounded" data-id="${sale.id}">Delete</button>
            `;
            salesList.appendChild(li);
        });
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', deleteSale);
        });
    });
}

function deleteSale(e) {
    const saleId = e.target.getAttribute('data-id');
    if (confirm('Are you sure you want to delete this sale?')) {
        fetch('/delete_sale', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: saleId }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Sale deleted successfully!');
                document.getElementById('getDailySalesForm').dispatchEvent(new Event('submit'));
            } else {
                alert('Error deleting sale: ' + data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while deleting the sale.');
        });
    }
}

function handleGetMonthlyTotal(e) {
    e.preventDefault();
    const monthYear = document.getElementById('monthYear').value;
    const [year, month] = monthYear.split('-');

    fetch(`/get_monthly_total?year=${year}&month=${month}`)
    .then(response => response.json())
    .then(data => {
        document.getElementById('monthlyTotal').textContent = `Total sales for ${monthYear}: KES ${data.total.toFixed(2)}`;
    });
}

function handleGetYearlyTotal(e) {
    e.preventDefault();
    const year = document.getElementById('year').value;

    fetch(`/get_yearly_total?year=${year}`)
    .then(response => response.json())
    .then(data => {
        document.getElementById('yearlyTotal').textContent = `Total sales for ${year}: KES ${data.total.toFixed(2)}`;
    });
}
